from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models import ATSAnalysis, JobDescription, Resume, User
from services.ats_service import analyze_resume
from utils.validation import is_valid_url, normalize_url


ats_bp = Blueprint("ats", __name__, url_prefix="/api")


def _payload() -> dict:
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def _user() -> User | None:
    return db.session.get(User, int(get_jwt_identity()))


def _job_or_404(user_id: int, job_id: int) -> JobDescription | None:
    return JobDescription.query.filter_by(id=job_id, user_id=user_id).first()


@ats_bp.get("/job-descriptions")
@jwt_required()
def list_jobs():
    user = _user()
    return jsonify({"items": [job.to_dict() for job in JobDescription.query.filter_by(user_id=user.id).order_by(JobDescription.updated_at.desc()).all()]})


@ats_bp.post("/job-descriptions")
@jwt_required()
def create_job():
    user = _user()
    data = _payload()
    title, description = (data.get("title") or "").strip(), (data.get("description") or "").strip()
    if not title or not description:
        return jsonify({"error": "validation_error", "message": "title and description are required"}), 400
    source_url = (data.get("source_url") or "").strip() or None
    if source_url:
        source_url = normalize_url(source_url)
        if not is_valid_url(source_url):
            return jsonify({"error": "validation_error", "message": "source_url must be valid"}), 400
    job = JobDescription(user_id=user.id, title=title, company=(data.get("company") or "").strip() or None, description=description, source_url=source_url)
    db.session.add(job); db.session.commit()
    return jsonify({"job_description": job.to_dict()}), 201


@ats_bp.get("/job-descriptions/<int:job_id>")
@jwt_required()
def get_job(job_id: int):
    user = _user(); job = _job_or_404(user.id, job_id)
    if job is None: return jsonify({"error": "not_found", "message": "Job description not found"}), 404
    return jsonify({"job_description": job.to_dict()})


@ats_bp.patch("/job-descriptions/<int:job_id>")
@jwt_required()
def update_job(job_id: int):
    user = _user(); job = _job_or_404(user.id, job_id)
    if job is None: return jsonify({"error": "not_found", "message": "Job description not found"}), 404
    data = _payload()
    for field in ("title", "company", "description"):
        if field in data:
            value = (data.get(field) or "").strip() or None
            if field in {"title", "description"} and not value: return jsonify({"error": "validation_error", "message": f"{field} cannot be empty"}), 400
            setattr(job, field, value)
    if "source_url" in data:
        value = (data.get("source_url") or "").strip() or None
        if value:
            value = normalize_url(value)
            if not is_valid_url(value): return jsonify({"error": "validation_error", "message": "source_url must be valid"}), 400
        job.source_url = value
    db.session.commit(); return jsonify({"job_description": job.to_dict()})


@ats_bp.delete("/job-descriptions/<int:job_id>")
@jwt_required()
def delete_job(job_id: int):
    user = _user(); job = _job_or_404(user.id, job_id)
    if job is None: return jsonify({"error": "not_found", "message": "Job description not found"}), 404
    db.session.delete(job); db.session.commit(); return jsonify({"deleted": True, "id": job_id})


@ats_bp.post("/resumes/<int:resume_id>/ats-analyses")
@jwt_required()
def create_analysis(resume_id: int):
    user = _user(); resume = Resume.query.filter_by(id=resume_id, user_id=user.id).first()
    if resume is None: return jsonify({"error": "not_found", "message": "Resume not found"}), 404
    job_id = _payload().get("job_description_id")
    try: job = _job_or_404(user.id, int(job_id))
    except (TypeError, ValueError): job = None
    if job is None: return jsonify({"error": "validation_error", "message": "A valid job_description_id is required"}), 400
    result = analyze_resume(resume, job.description)
    analysis = ATSAnalysis(user_id=user.id, resume_id=resume.id, job_description_id=job.id, **result)
    resume.ats_score = result["score"]
    db.session.add(analysis); db.session.commit()
    return jsonify({"analysis": analysis.to_dict()}), 201


@ats_bp.get("/resumes/<int:resume_id>/ats-analyses")
@jwt_required()
def list_analyses(resume_id: int):
    user = _user(); resume = Resume.query.filter_by(id=resume_id, user_id=user.id).first()
    if resume is None: return jsonify({"error": "not_found", "message": "Resume not found"}), 404
    items = ATSAnalysis.query.filter_by(user_id=user.id, resume_id=resume.id).order_by(ATSAnalysis.created_at.desc()).all()
    return jsonify({"items": [item.to_dict() for item in items]})
