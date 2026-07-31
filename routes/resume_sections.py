from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from services.pdf_service import delete_managed_pdf
from models import Certificate, Education, Experience, GeneratedPDF, Language, Project, Resume, Skill, User
from utils.validation import contains_first_person_pronoun, count_words, is_valid_url, normalize_url

sections_bp = Blueprint("sections", __name__)


def _extract_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _current_user() -> User | None:
    user_id = int(get_jwt_identity())
    return db.session.get(User, user_id)


def _owned_resume(user: User, resume_id: int) -> Resume | None:
    return Resume.query.filter_by(id=resume_id, user_id=user.id).first()


def _owned_resume_or_404(resume_id: int) -> tuple[User | None, Resume | None, tuple[dict, int] | None]:
    user = _current_user()
    if user is None:
        return None, None, ({"error": "not_found", "message": "User not found"}, 404)

    resume = _owned_resume(user, resume_id)
    if resume is None:
        return user, None, ({"error": "not_found", "message": "Resume not found"}, 404)

    return user, resume, None


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


def _validate_url_fields(payload: dict, fields: tuple[str, ...]) -> tuple[dict, int] | None:
    for field in fields:
        value = payload.get(field)
        if value:
            normalized = normalize_url(str(value))
            if not is_valid_url(normalized):
                return {"error": "validation_error", "message": f"{field} must be a valid URL"}, 400
            payload[field] = normalized
    return None


def _validate_achievement_bullets(achievements: object) -> tuple[dict, int] | None:
    if achievements is None:
        return {"error": "validation_error", "message": "achievements are required"}, 400
    if not isinstance(achievements, list):
        return {"error": "validation_error", "message": "achievements must be a list of bullet points"}, 400
    if len(achievements) < 2 or len(achievements) > 6:
        return {"error": "validation_error", "message": "achievements must contain between 2 and 6 bullet points"}, 400

    for bullet in achievements:
        if not isinstance(bullet, str) or not bullet.strip():
            return {"error": "validation_error", "message": "achievement bullets cannot be empty"}, 400
        bullet_words = count_words(bullet)
        if bullet_words < 10 or bullet_words > 30:
            return {"error": "validation_error", "message": "each achievement bullet must be between 10 and 30 words"}, 400
    return None


def _normalize_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    value = str(value).strip()
    return value or None


def _normalize_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError


def _normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _normalize_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError


def _normalize_json(value: object) -> object:
    if value in (None, ""):
        return {}
    if isinstance(value, (dict, list)):
        return value
    raise ValueError


def _build_data(payload: dict, partial: bool, required_strings: tuple[str, ...], optional_strings: tuple[str, ...], optional_dates: tuple[str, ...], optional_bools: tuple[str, ...], optional_ints: tuple[str, ...], optional_json: tuple[str, ...]) -> tuple[dict | None, tuple[dict, int] | None]:
    data: dict = {}

    for field in required_strings:
        if partial and field not in payload:
            continue
        if field not in payload:
            return None, ({"error": "validation_error", "message": f"{field} is required"}, 400)
        value = _normalize_string(payload.get(field))
        if value is None:
            return None, ({"error": "validation_error", "message": f"{field} cannot be empty"}, 400)
        data[field] = value

    for field in optional_strings:
        if field in payload:
            data[field] = _normalize_string(payload.get(field))

    for field in optional_dates:
        if field in payload:
            try:
                data[field] = _normalize_date(payload.get(field))
            except ValueError:
                return None, ({"error": "validation_error", "message": f"{field} must be an ISO date"}, 400)

    for field in optional_bools:
        if field in payload:
            data[field] = _normalize_bool(payload.get(field))

    for field in optional_ints:
        if field in payload:
            try:
                data[field] = _normalize_int(payload.get(field))
            except ValueError:
                return None, ({"error": "validation_error", "message": f"{field} must be an integer"}, 400)

    for field in optional_json:
        if field in payload:
            try:
                data[field] = _normalize_json(payload.get(field))
            except ValueError:
                return None, ({"error": "validation_error", "message": f"{field} must be a JSON object or array"}, 400)

    return data, None


def _query_section(model, resume_id: int, item_id: int | None = None, user_id: int | None = None):
    query = model.query.filter_by(resume_id=resume_id)
    if item_id is not None:
        query = query.filter_by(id=item_id)
    if user_id is not None and hasattr(model, "user_id"):
        query = query.filter_by(user_id=user_id)
    return query


def _list_endpoint(model, serializer_name: str, order_by: str = "sort_order", descending: bool = False):
    def view(resume_id: int):
        user, resume, error = _owned_resume_or_404(resume_id)
        if error is not None:
            return jsonify(error[0]), error[1]

        order_column = getattr(model, order_by)
        order_clause = order_column.desc() if descending else order_column.asc()
        items = _query_section(model, resume.id).order_by(order_clause, model.id.asc()).all()
        return jsonify({"items": [item.to_dict() for item in items]})

    view.__name__ = f"list_{serializer_name}"
    return jwt_required()(view)


def _create_endpoint(model, serializer_name: str, required_strings: tuple[str, ...], optional_strings: tuple[str, ...] = (), optional_dates: tuple[str, ...] = (), optional_bools: tuple[str, ...] = (), optional_ints: tuple[str, ...] = (), optional_json: tuple[str, ...] = (), extra_fields: tuple[str, ...] = (), order_defaults: dict[str, object] | None = None):
    def view(resume_id: int):
        user, resume, error = _owned_resume_or_404(resume_id)
        if error is not None:
            return jsonify(error[0]), error[1]

        payload = _extract_payload()
        data, parse_error = _build_data(payload, False, required_strings, optional_strings, optional_dates, optional_bools, optional_ints, optional_json)
        if parse_error is not None:
            return jsonify(parse_error[0]), parse_error[1]

        if model is Experience:
            achievements_error = _validate_achievement_bullets(data.get("achievements"))
            if achievements_error is not None:
                return jsonify(achievements_error[0]), achievements_error[1]

        if model in {Project, Certificate}:
            link_error = _validate_url_fields(data, ("url", "credential_url"))
            if link_error is not None:
                return jsonify(link_error[0]), link_error[1]

        if order_defaults:
            for field, value in order_defaults.items():
                data.setdefault(field, value)

        data["resume_id"] = resume.id
        if "user_id" in extra_fields:
            data["user_id"] = user.id

        item = model(**data)
        db.session.add(item)
        db.session.commit()
        return jsonify({serializer_name: item.to_dict()}), 201

    view.__name__ = f"create_{serializer_name}"
    return jwt_required()(view)


def _get_endpoint(model, serializer_name: str):
    def view(resume_id: int, item_id: int):
        user, resume, error = _owned_resume_or_404(resume_id)
        if error is not None:
            return jsonify(error[0]), error[1]

        item = _query_section(model, resume.id, item_id=item_id).first()
        if item is None:
            return jsonify({"error": "not_found", "message": f"{serializer_name.title()} not found"}), 404

        return jsonify({serializer_name: item.to_dict()})

    view.__name__ = f"get_{serializer_name}"
    return jwt_required()(view)


def _update_endpoint(model, serializer_name: str, required_strings: tuple[str, ...], optional_strings: tuple[str, ...] = (), optional_dates: tuple[str, ...] = (), optional_bools: tuple[str, ...] = (), optional_ints: tuple[str, ...] = (), optional_json: tuple[str, ...] = ()):
    def view(resume_id: int, item_id: int):
        user, resume, error = _owned_resume_or_404(resume_id)
        if error is not None:
            return jsonify(error[0]), error[1]

        item = _query_section(model, resume.id, item_id=item_id).first()
        if item is None:
            return jsonify({"error": "not_found", "message": f"{serializer_name.title()} not found"}), 404

        payload = _extract_payload()
        data, parse_error = _build_data(payload, True, required_strings, optional_strings, optional_dates, optional_bools, optional_ints, optional_json)
        if parse_error is not None:
            return jsonify(parse_error[0]), parse_error[1]

        if model is Experience and "achievements" in data:
            achievements_error = _validate_achievement_bullets(data.get("achievements"))
            if achievements_error is not None:
                return jsonify(achievements_error[0]), achievements_error[1]

        if model in {Project, Certificate}:
            link_error = _validate_url_fields(data, ("url", "credential_url"))
            if link_error is not None:
                return jsonify(link_error[0]), link_error[1]

        for key, value in data.items():
            setattr(item, key, value)

        db.session.commit()
        return jsonify({serializer_name: item.to_dict()})

    view.__name__ = f"update_{serializer_name}"
    return jwt_required()(view)


def _delete_endpoint(model, serializer_name: str):
    def view(resume_id: int, item_id: int):
        user, resume, error = _owned_resume_or_404(resume_id)
        if error is not None:
            return jsonify(error[0]), error[1]

        item = _query_section(model, resume.id, item_id=item_id).first()
        if item is None:
            return jsonify({"error": "not_found", "message": f"{serializer_name.title()} not found"}), 404

        db.session.delete(item)
        db.session.commit()
        return jsonify({"deleted": True, "id": item_id})

    view.__name__ = f"delete_{serializer_name}"
    return jwt_required()(view)


_SECTION_SPECS = [
    {
        "name": "experiences",
        "model": Experience,
        "item_name": "experience",
        "required_strings": ("company", "job_title"),
        "optional_strings": ("location", "description"),
        "optional_dates": ("start_date", "end_date"),
        "optional_bools": ("is_current",),
        "optional_ints": ("sort_order",),
        "optional_json": ("achievements",),
        "order_by": "sort_order",
    },
    {
        "name": "educations",
        "model": Education,
        "item_name": "education",
        "required_strings": ("institution",),
        "optional_strings": ("degree", "field_of_study", "location", "gpa", "description"),
        "optional_dates": ("start_date", "end_date"),
        "optional_ints": ("sort_order",),
        "order_by": "sort_order",
    },
    {
        "name": "projects",
        "model": Project,
        "item_name": "project",
        "required_strings": ("name",),
        "optional_strings": ("description", "url"),
        "optional_ints": ("sort_order",),
        "optional_json": ("tech_stack",),
        "order_by": "sort_order",
    },
    {
        "name": "skills",
        "model": Skill,
        "item_name": "skill",
        "required_strings": ("name",),
        "optional_strings": ("category", "proficiency"),
        "optional_ints": ("sort_order",),
        "order_by": "sort_order",
    },
    {
        "name": "certificates",
        "model": Certificate,
        "item_name": "certificate",
        "required_strings": ("name",),
        "optional_strings": ("issuer", "credential_id", "credential_url"),
        "optional_dates": ("issue_date", "expiry_date"),
        "optional_ints": ("sort_order",),
        "order_by": "sort_order",
    },
    {
        "name": "languages",
        "model": Language,
        "item_name": "language",
        "required_strings": ("name",),
        "optional_strings": ("proficiency",),
        "optional_ints": ("sort_order",),
        "order_by": "sort_order",
    },
]


for spec in _SECTION_SPECS:
    collection = spec["name"]
    item_name = spec["item_name"]
    model = spec["model"]

    sections_bp.add_url_rule(
        f"/api/resumes/<int:resume_id>/{collection}",
        endpoint=f"list_{collection}",
        view_func=_list_endpoint(model, item_name, order_by=spec.get("order_by", "sort_order")),
        methods=["GET"],
    )
    sections_bp.add_url_rule(
        f"/api/resumes/<int:resume_id>/{collection}",
        endpoint=f"create_{collection}",
        view_func=_create_endpoint(
            model,
            item_name,
            spec.get("required_strings", ()),
            spec.get("optional_strings", ()),
            spec.get("optional_dates", ()),
            spec.get("optional_bools", ()),
            spec.get("optional_ints", ()),
            spec.get("optional_json", ()),
            order_defaults={"sort_order": 0} if "sort_order" in spec.get("optional_ints", ()) else None,
        ),
        methods=["POST"],
    )
    sections_bp.add_url_rule(
        f"/api/resumes/<int:resume_id>/{collection}/<int:item_id>",
        endpoint=f"get_{collection}",
        view_func=_get_endpoint(model, item_name),
        methods=["GET"],
    )
    sections_bp.add_url_rule(
        f"/api/resumes/<int:resume_id>/{collection}/<int:item_id>",
        endpoint=f"update_{collection}",
        view_func=_update_endpoint(
            model,
            item_name,
            spec.get("required_strings", ()),
            spec.get("optional_strings", ()),
            spec.get("optional_dates", ()),
            spec.get("optional_bools", ()),
            spec.get("optional_ints", ()),
            spec.get("optional_json", ()),
        ),
        methods=["PATCH"],
    )
    sections_bp.add_url_rule(
        f"/api/resumes/<int:resume_id>/{collection}/<int:item_id>",
        endpoint=f"delete_{collection}",
        view_func=_delete_endpoint(model, item_name),
        methods=["DELETE"],
    )


def _generated_pdf_list(resume_id: int):
    user, resume, error = _owned_resume_or_404(resume_id)
    if error is not None:
        return jsonify(error[0]), error[1]

    pdfs = GeneratedPDF.query.filter_by(resume_id=resume.id, user_id=user.id).order_by(GeneratedPDF.generated_at.desc(), GeneratedPDF.id.desc()).all()
    return jsonify({"items": [pdf.to_dict() for pdf in pdfs]})


sections_bp.add_url_rule(
    "/api/resumes/<int:resume_id>/generated-pdfs",
    endpoint="list_generated_pdfs",
    view_func=jwt_required()(_generated_pdf_list),
    methods=["GET"],
)


def _get_generated_pdf(resume_id: int, item_id: int):
    user, resume, error = _owned_resume_or_404(resume_id)
    if error is not None:
        return jsonify(error[0]), error[1]

    pdf = GeneratedPDF.query.filter_by(resume_id=resume.id, user_id=user.id, id=item_id).first()
    if pdf is None:
        return jsonify({"error": "not_found", "message": "Generated PDF not found"}), 404

    return jsonify({"generated_pdf": pdf.to_dict()})


sections_bp.add_url_rule(
    "/api/resumes/<int:resume_id>/generated-pdfs/<int:item_id>",
    endpoint="get_generated_pdf",
    view_func=jwt_required()(_get_generated_pdf),
    methods=["GET"],
)


def _delete_generated_pdf(resume_id: int, item_id: int):
    user, resume, error = _owned_resume_or_404(resume_id)
    if error is not None:
        return jsonify(error[0]), error[1]

    pdf = GeneratedPDF.query.filter_by(resume_id=resume.id, user_id=user.id, id=item_id).first()
    if pdf is None:
        return jsonify({"error": "not_found", "message": "Generated PDF not found"}), 404

    delete_managed_pdf(pdf.file_path)
    db.session.delete(pdf)
    db.session.commit()
    return jsonify({"deleted": True, "id": item_id})


sections_bp.add_url_rule(
    "/api/resumes/<int:resume_id>/generated-pdfs/<int:item_id>",
    endpoint="delete_generated_pdf",
    view_func=jwt_required()(_delete_generated_pdf),
    methods=["DELETE"],
)
