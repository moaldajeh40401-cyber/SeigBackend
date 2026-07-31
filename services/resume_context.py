from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from models import Resume


SECTION_ORDER = (
    "professional_summary",
    "skills",
    "experiences",
    "projects",
    "educations",
    "certificates",
    "languages",
)


def format_month_year(value: date | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%b %Y")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    return [value]


def _normalize_text_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in _as_list(value):
        if item is None:
            continue
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def _normalize_tech_stack(value: Any) -> list[str]:
    return _normalize_text_list(value)


def _serialize_personal_info(resume: Resume) -> dict[str, Any]:
    user = resume.user
    return {
        "full_name": user.full_name if user else "YOUR NAME",
        "email": user.email if user else None,
        "phone_number": user.phone_number if user else None,
        "location": user.location if user else None,
        "linkedin_url": resume.linkedin_url,
        "github_url": resume.github_url,
        "portfolio_url": resume.portfolio_url,
        "website_url": resume.website_url,
    }


def _serialize_experience(experience: Any) -> dict[str, Any]:
    data = experience.to_dict() if hasattr(experience, "to_dict") else {}
    data["achievements"] = _normalize_text_list(data.get("achievements"))
    return data


def _serialize_education(education: Any) -> dict[str, Any]:
    data = education.to_dict() if hasattr(education, "to_dict") else {}
    return data


def _serialize_project(project: Any) -> dict[str, Any]:
    data = project.to_dict() if hasattr(project, "to_dict") else {}
    data["tech_stack"] = _normalize_tech_stack(data.get("tech_stack"))
    return data


def _serialize_skill(skill: Any) -> dict[str, Any]:
    return skill.to_dict() if hasattr(skill, "to_dict") else {}


def _serialize_certificate(certificate: Any) -> dict[str, Any]:
    return certificate.to_dict() if hasattr(certificate, "to_dict") else {}


def _serialize_language(language: Any) -> dict[str, Any]:
    return language.to_dict() if hasattr(language, "to_dict") else {}


def build_resume_context(resume: Resume) -> dict[str, Any]:
    return {
        "id": resume.id,
        "title": resume.title,
        "target_role": resume.target_role,
        "professional_summary": resume.professional_summary,
        "status": resume.status,
        "version": resume.version,
        "ats_score": resume.ats_score,
        "user": _serialize_personal_info(resume),
        "experiences": [_serialize_experience(item) for item in resume.experiences],
        "educations": [_serialize_education(item) for item in resume.educations],
        "projects": [_serialize_project(item) for item in resume.projects],
        "skills": [_serialize_skill(item) for item in resume.skills],
        "certificates": [_serialize_certificate(item) for item in resume.certificates],
        "languages": [_serialize_language(item) for item in resume.languages],
        "contact_line": _build_contact_line(resume),
    }


def _build_contact_line(resume: Resume) -> str:
    user = resume.user
    parts = []
    if user and user.location:
        parts.append(user.location)
    if user and user.email:
        parts.append(user.email)
    if user and user.phone_number:
        parts.append(user.phone_number)
    if resume.linkedin_url:
        parts.append(resume.linkedin_url)
    if resume.github_url:
        parts.append(resume.github_url)
    if resume.portfolio_url:
        parts.append(resume.portfolio_url)
    if resume.website_url:
        parts.append(resume.website_url)
    return " | ".join(parts)
