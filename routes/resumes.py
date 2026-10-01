from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from hashlib import sha256
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db, limiter
from models import Education, Experience, GeneratedPDF, Language, Project, Resume, Skill, Template, User
from services.pdf_service import (
    build_resume_pdf_bytes,
    delete_managed_pdf,
    ensure_generated_dir,
    is_managed_pdf_path,
)
from services.resume_context import build_resume_context
from utils.validation import contains_first_person_pronoun, count_words, is_valid_url, normalize_url

resumes_bp = Blueprint("resumes", __name__, url_prefix="/api/resumes")


def _extract_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _current_user() -> User | None:
    user_id = int(get_jwt_identity())
    return db.session.get(User, user_id)


def _owned_resume_or_404(user_id: int, resume_id: int) -> Resume | None:
    return Resume.query.filter_by(id=resume_id, user_id=user_id).first()


def _resolve_template_for_resume(resume: Resume) -> Template:
    if resume.template is not None:
        return resume.template

    default_template = Template.query.filter_by(name="classic").first()
    if default_template is not None:
        return default_template

    active_template = Template.query.filter_by(is_active=True).order_by(Template.name.asc()).first()
    if active_template is not None:
        return active_template

    return Template(name="classic", display_name="Classic", template_path="classic.html", css_path="static/css/templates/classic.css", description="Default ATS layout")


def _resolve_template_id(payload: dict) -> tuple[int | None, tuple[dict, int] | None]:
    if "template_id" in payload:
        raw_template_id = payload.get("template_id")
        if raw_template_id in (None, ""):
            return None, None
        try:
            template = db.session.get(Template, int(raw_template_id))
        except (TypeError, ValueError):
            return None, ({"error": "validation_error", "message": "template_id must be an integer"}, 400)
        if template is None or not template.is_active:
            return None, ({"error": "validation_error", "message": "Selected template is unavailable"}, 400)
        return template.id, None

    template_path = (payload.get("template_path") or "").strip()
    if template_path:
        template = Template.query.filter_by(template_path=template_path).first()
        if template is None or not template.is_active:
            return None, ({"error": "validation_error", "message": "Selected template is unavailable"}, 400)
        return template.id, None

    template_name = (payload.get("template_name") or "").strip()
    if not template_name:
        return None, None

    template = Template.query.filter_by(name=template_name).first()
    if template is None or not template.is_active:
        return None, ({"error": "validation_error", "message": "Selected template is unavailable"}, 400)
    return template.id, None


def _normalize_ats_score(value: object) -> tuple[float | None, tuple[dict, int] | None]:
    if value in (None, ""):
        return None, None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None, ({"error": "validation_error", "message": "ats_score must be a number"}, 400)
    if not 0 <= score <= 100:
        return None, ({"error": "validation_error", "message": "ats_score must be between 0 and 100"}, 400)
    return score, None


def _normalize_status(value: object) -> str:
    status = (value or "draft")
    if not isinstance(status, str):
        status = str(status)
    status = status.strip().lower() or "draft"
    if status not in {"draft", "completed", "archived"}:
        return "draft"
    return status


def _normalize_version(value: object) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError):
        version = 1
    return max(version, 1)


def _validate_summary(summary: str | None) -> tuple[dict, int] | None:
    if summary is None:
        return None

    word_count = count_words(summary)
    sentence_count = len([part for part in summary.split(".") if part.strip()])
    if word_count < 50 or word_count > 150:
        return {"error": "validation_error", "message": "professional_summary must be between 50 and 150 words"}, 400
    if sentence_count < 2 or sentence_count > 4:
        return {"error": "validation_error", "message": "professional_summary must contain 2 to 4 sentences"}, 400
    if contains_first_person_pronoun(summary):
        return {"error": "validation_error", "message": "professional_summary cannot use first-person pronouns"}, 400
    return None


def _validate_links(payload: dict) -> tuple[dict, int] | None:
    for field in ("linkedin_url", "github_url", "portfolio_url", "website_url"):
        value = payload.get(field)
        if value:
            normalized = normalize_url(str(value))
            if not is_valid_url(normalized):
                return {"error": "validation_error", "message": f"{field} must be a valid URL"}, 400
            payload[field] = normalized
    return None


def _render_resume_html(resume: Resume, template: Template) -> str:
    template_name = template.template_path.removeprefix("templates/")
    if template_name != "classic.html":
        raise ValueError("Template is not a supported resume layout")
    css_file = Path(current_app.static_folder) / "css" / "templates" / f"{template.name}.css"
    css_path = css_file.resolve().as_uri() if css_file.exists() else None
    return render_template(template_name, resume=build_resume_context(resume), css_path=css_path, template=template)


@resumes_bp.post("/export")
@jwt_required()
@limiter.limit("5 per hour")
def export_resume(resume_id: int | None = None):
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    payload = _extract_payload()
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "validation_error", "message": "title is required"}), 400

    links = {field: (payload.get(field) or "").strip() or None for field in ("linkedin_url", "github_url", "portfolio_url", "website_url")}
    link_error = _validate_links(links)
    if link_error is not None:
        return jsonify(link_error[0]), link_error[1]
    summary = (payload.get("professional_summary") or "").strip() or None
    summary_error = _validate_summary(summary)
    if summary_error is not None:
        return jsonify(summary_error[0]), summary_error[1]

    def parse_date(value):
        if not value:
            return None
        try:
            normalized = str(value)
            if len(normalized) == 7:
                normalized = f"{normalized}-01"
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            return None

    resume = Resume(
        user_id=user.id,
        title=title,
        target_role=(payload.get("target_role") or "").strip() or None,
        professional_summary=summary,
        status=_normalize_status(payload.get("status")),
        **links,
    )
    for item in payload.get("experiences", []):
        if not item.get("company") or not item.get("job_title"):
            return jsonify({"error": "validation_error", "message": "experience company and job_title are required"}), 400
        resume.experiences.append(Experience(
            company=str(item["company"]).strip(), job_title=str(item["job_title"]).strip(),
            location=(item.get("location") or "").strip() or None, start_date=parse_date(item.get("start_date")),
            end_date=parse_date(item.get("end_date")), is_current=bool(item.get("is_current")),
            achievements=item.get("achievements") if isinstance(item.get("achievements"), list) else [],
            sort_order=int(item.get("sort_order", 0)),
        ))
    for item in payload.get("educations", []):
        if not item.get("institution"):
            return jsonify({"error": "validation_error", "message": "education institution is required"}), 400
        resume.educations.append(Education(
            institution=str(item["institution"]).strip(), degree=(item.get("degree") or "").strip() or None,
            field_of_study=(item.get("field_of_study") or "").strip() or None, location=(item.get("location") or "").strip() or None,
            start_date=parse_date(item.get("start_date")), end_date=parse_date(item.get("end_date")), sort_order=int(item.get("sort_order", 0)),
        ))
    for item in payload.get("skills", []):
        if item.get("name"):
            resume.skills.append(Skill(name=str(item["name"]).strip(), sort_order=int(item.get("sort_order", 0))))
    for item in payload.get("languages", []):
        if item.get("name"):
            resume.languages.append(Language(name=str(item["name"]).strip(), proficiency=(item.get("proficiency") or "").strip() or None, sort_order=int(item.get("sort_order", 0))))
    for item in payload.get("projects", []):
        if item.get("name"):
            tech_stack = item.get("tech_stack") if isinstance(item.get("tech_stack"), dict) else ({"value": item.get("tech_stack")} if item.get("tech_stack") else {})
            resume.projects.append(Project(name=str(item["name"]).strip(), description=(item.get("description") or "").strip() or None, url=(item.get("url") or "").strip() or None, tech_stack=tech_stack, sort_order=int(item.get("sort_order", 0))))

    db.session.add(resume)
    db.session.commit()
    template = _resolve_template_for_resume(resume)
    try:
        pdf_bytes = build_resume_pdf_bytes(_render_resume_html(resume, template))
    except ValueError as error:
        return jsonify({"error": "invalid_template", "message": str(error)}), 500
    except RuntimeError as error:
        return jsonify({"error": "pdf_unavailable", "message": str(error)}), 503

    generated_dir = ensure_generated_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    file_name = f"resume_{resume.id}_v{resume.version}_{timestamp}.pdf"
    file_path = generated_dir / file_name
    file_path.write_bytes(pdf_bytes)
    db.session.add(GeneratedPDF(user_id=user.id, resume_id=resume.id, file_path=str(file_path), file_name=file_name, file_size=len(pdf_bytes), checksum=sha256(pdf_bytes).hexdigest()))
    db.session.commit()
    return send_file(BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name=file_name, max_age=0)


@resumes_bp.get("")
@jwt_required()
def list_resumes():
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.updated_at.desc()).all()
    return jsonify({"items": [resume.to_dict() for resume in resumes]})


@resumes_bp.post("")
@jwt_required()
def create_resume():
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    payload = _extract_payload()
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "validation_error", "message": "title is required"}), 400

    template_id, template_error = _resolve_template_id(payload)
    if template_error is not None:
        return jsonify(template_error[0]), template_error[1]
    ats_score, score_error = _normalize_ats_score(payload.get("ats_score"))
    if score_error is not None:
        return jsonify(score_error[0]), score_error[1]

    links = {field: (payload.get(field) or "").strip() or None for field in ("linkedin_url", "github_url", "portfolio_url", "website_url")}
    link_error = _validate_links(links)
    if link_error is not None:
        return jsonify(link_error[0]), link_error[1]

    resume = Resume(
        user_id=user.id,
        title=title,
        target_role=(payload.get("target_role") or "").strip() or None,
        template_id=template_id,
        professional_summary=(payload.get("professional_summary") or "").strip() or None,
        **links,
        status=_normalize_status(payload.get("status")),
        version=_normalize_version(payload.get("version")),
        ats_score=ats_score,
    )

    summary_error = _validate_summary(resume.professional_summary)
    if summary_error is not None:
        return jsonify(summary_error[0]), summary_error[1]

    db.session.add(resume)
    db.session.commit()
    return jsonify({"resume": resume.to_dict()}), 201


@resumes_bp.get("/<int:resume_id>")
@jwt_required()
def get_resume(resume_id: int):
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    resume = _owned_resume_or_404(user.id, resume_id)
    if resume is None:
        return jsonify({"error": "not_found", "message": "Resume not found"}), 404

    return jsonify({"resume": resume.to_dict()})


@resumes_bp.patch("/<int:resume_id>")
@jwt_required()
def update_resume(resume_id: int):
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    resume = _owned_resume_or_404(user.id, resume_id)
    if resume is None:
        return jsonify({"error": "not_found", "message": "Resume not found"}), 404

    payload = _extract_payload()
    if "title" in payload:
        title = (payload.get("title") or "").strip()
        if not title:
            return jsonify({"error": "validation_error", "message": "title cannot be empty"}), 400
        resume.title = title

    if "target_role" in payload:
        resume.target_role = (payload.get("target_role") or "").strip() or None

    if "professional_summary" in payload:
        resume.professional_summary = (payload.get("professional_summary") or "").strip() or None
        summary_error = _validate_summary(resume.professional_summary)
        if summary_error is not None:
            return jsonify(summary_error[0]), summary_error[1]

    if "linkedin_url" in payload:
        resume.linkedin_url = (payload.get("linkedin_url") or "").strip() or None

    if "github_url" in payload:
        resume.github_url = (payload.get("github_url") or "").strip() or None

    if "portfolio_url" in payload:
        resume.portfolio_url = (payload.get("portfolio_url") or "").strip() or None

    if "website_url" in payload:
        resume.website_url = (payload.get("website_url") or "").strip() or None

    links = {
            "linkedin_url": resume.linkedin_url,
            "github_url": resume.github_url,
            "portfolio_url": resume.portfolio_url,
            "website_url": resume.website_url,
        }
    link_error = _validate_links(links)
    if link_error is not None:
        return jsonify(link_error[0]), link_error[1]
    for field, value in links.items():
        setattr(resume, field, value)

    if "status" in payload:
        resume.status = _normalize_status(payload.get("status"))

    if "version" in payload:
        resume.version = _normalize_version(payload.get("version"))

    if "template_id" in payload or "template_name" in payload or "template_path" in payload:
        template_id, template_error = _resolve_template_id(payload)
        if template_error is not None:
            return jsonify(template_error[0]), template_error[1]
        resume.template_id = template_id

    if "ats_score" in payload:
        ats_score, score_error = _normalize_ats_score(payload.get("ats_score"))
        if score_error is not None:
            return jsonify(score_error[0]), score_error[1]
        resume.ats_score = ats_score

    db.session.commit()
    return jsonify({"resume": resume.to_dict()})


@resumes_bp.delete("/<int:resume_id>")
@jwt_required()
def delete_resume(resume_id: int):
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    resume = _owned_resume_or_404(user.id, resume_id)
    if resume is None:
        return jsonify({"error": "not_found", "message": "Resume not found"}), 404

    for generated_pdf in resume.generated_pdfs:
        delete_managed_pdf(generated_pdf.file_path)
    db.session.delete(resume)
    db.session.commit()
    return jsonify({"deleted": True, "resume_id": resume_id})


@resumes_bp.get("/<int:resume_id>/preview")
@jwt_required()
def preview_resume(resume_id: int):
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    resume = _owned_resume_or_404(user.id, resume_id)
    if resume is None:
        return jsonify({"error": "not_found", "message": "Resume not found"}), 404

    template = _resolve_template_for_resume(resume)
    try:
        html = _render_resume_html(resume, template)
    except (ValueError, RuntimeError) as error:
        return jsonify({"error": "invalid_template", "message": str(error)}), 500
    return html.replace(f"file:///{Path(current_app.static_folder).resolve().as_posix()}/", "/static/")


@resumes_bp.post("/<int:resume_id>/pdf")
@jwt_required()
@limiter.limit("5 per hour")
def generate_resume_pdf(resume_id: int):
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    resume = _owned_resume_or_404(user.id, resume_id)
    if resume is None:
        return jsonify({"error": "not_found", "message": "Resume not found"}), 404

    template = _resolve_template_for_resume(resume)
    try:
        pdf_bytes = build_resume_pdf_bytes(_render_resume_html(resume, template))
    except ValueError as error:
        return jsonify({"error": "invalid_template", "message": str(error)}), 500
    except RuntimeError as error:
        return jsonify({"error": "pdf_unavailable", "message": str(error)}), 503

    generated_dir = ensure_generated_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    file_name = f"resume_{resume.id}_v{resume.version}_{timestamp}.pdf"
    file_path = generated_dir / file_name
    file_path.write_bytes(pdf_bytes)

    generated_pdf = GeneratedPDF(
        user_id=user.id,
        resume_id=resume.id,
        file_path=str(file_path),
        file_name=file_name,
        file_size=len(pdf_bytes),
        checksum=sha256(pdf_bytes).hexdigest(),
    )
    db.session.add(generated_pdf)
    db.session.commit()

    return jsonify({"generated_pdf": generated_pdf.to_dict(), "message": "PDF generated successfully"}), 201


@resumes_bp.get("/<int:resume_id>/pdf/latest")
@jwt_required()
def latest_resume_pdf(resume_id: int):
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    resume = _owned_resume_or_404(user.id, resume_id)
    if resume is None:
        return jsonify({"error": "not_found", "message": "Resume not found"}), 404

    latest_pdf = (
        GeneratedPDF.query.filter_by(user_id=user.id, resume_id=resume.id)
        .order_by(GeneratedPDF.generated_at.desc(), GeneratedPDF.id.desc())
        .first()
    )
    if latest_pdf is None or not is_managed_pdf_path(latest_pdf.file_path):
        return jsonify({"error": "not_found", "message": "Generated PDF not found"}), 404

    return send_file(
        latest_pdf.file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=latest_pdf.file_name,
        max_age=0,
    )


@resumes_bp.get("/<int:resume_id>/download")
@jwt_required()
@limiter.limit("5 per hour")
def download_resume(resume_id: int):
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    resume = _owned_resume_or_404(user.id, resume_id)
    if resume is None:
        return jsonify({"error": "not_found", "message": "Resume not found"}), 404

    template = _resolve_template_for_resume(resume)
    try:
        pdf_bytes = build_resume_pdf_bytes(_render_resume_html(resume, template))
    except ValueError as error:
        return jsonify({"error": "invalid_template", "message": str(error)}), 500
    except RuntimeError as error:
        return jsonify({"error": "pdf_unavailable", "message": str(error)}), 503

    generated_dir = ensure_generated_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    file_name = f"resume_{resume.id}_v{resume.version}_{timestamp}.pdf"
    file_path = generated_dir / file_name
    file_path.write_bytes(pdf_bytes)

    generated_pdf = GeneratedPDF(
        user_id=user.id,
        resume_id=resume.id,
        file_path=str(file_path),
        file_name=file_name,
        file_size=len(pdf_bytes),
        checksum=sha256(pdf_bytes).hexdigest(),
    )
    db.session.add(generated_pdf)
    db.session.commit()

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=file_name,
        max_age=0,
    )


