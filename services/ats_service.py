from __future__ import annotations

import re

from models import Resume

STOP_WORDS = {"and", "the", "with", "for", "you", "your", "are", "that", "this", "from", "will", "have", "our", "job", "role", "work", "year", "years", "using", "experience", "required", "preferred", "skills", "team", "a", "an", "of", "to", "in", "on", "as", "is", "be"}


def _keywords(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z+#.]{2,}", text) if word.lower() not in STOP_WORDS}


def _json_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(str(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    return str(value or "")


def analyze_resume(resume: Resume, job_description: str) -> dict:
    resume_parts = [resume.title, resume.target_role, resume.professional_summary]
    resume_parts.extend(f"{item.job_title} {item.company} {item.description or ''} {_json_text(item.achievements)}" for item in resume.experiences)
    resume_parts.extend(f"{item.name} {item.category or ''}" for item in resume.skills)
    resume_parts.extend(f"{item.name} {item.description or ''} {_json_text(item.tech_stack)}" for item in resume.projects)
    required = _keywords(job_description)
    present = _keywords(" ".join(part or "" for part in resume_parts))
    matched = sorted(required & present)
    missing = sorted(required - present)
    fields = {"contact": bool(resume.user and resume.user.email and resume.user.phone_number), "summary": bool(resume.professional_summary), "experience": bool(resume.experiences), "skills": bool(resume.skills), "education": bool(resume.educations)}
    keyword_score = len(matched) / len(required) * 80 if required else 0
    completeness_score = sum(fields.values()) / len(fields) * 20
    return {"score": round(keyword_score + completeness_score, 1), "matched_keywords": {"items": matched}, "missing_keywords": {"items": missing}, "completeness": fields}
