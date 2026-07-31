from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.ext.mutable import MutableDict

from extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_month_year(value: date | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%b %Y")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(40), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    resumes = db.relationship(
        "Resume",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    generated_pdfs = db.relationship(
        "GeneratedPDF",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    job_descriptions = db.relationship("JobDescription", back_populates="user", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "location": self.location,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(255), nullable=False)
    template_path = db.Column(db.String(512), nullable=False)
    css_path = db.Column(db.String(512), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    resumes = db.relationship("Resume", back_populates="template", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "template_path": self.template_path,
            "css_path": self.css_path,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Resume(db.Model):
    __tablename__ = "resumes"

    __table_args__ = (
        db.CheckConstraint("version >= 1", name="ck_resumes_version_min"),
        db.Index("ix_resume_user_title", "user_id", "title"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id = db.Column(
        db.Integer,
        db.ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = db.Column(db.String(255), nullable=False)
    target_role = db.Column(db.String(255), nullable=True)
    professional_summary = db.Column(db.Text, nullable=True)
    linkedin_url = db.Column(db.String(512), nullable=True)
    github_url = db.Column(db.String(512), nullable=True)
    portfolio_url = db.Column(db.String(512), nullable=True)
    website_url = db.Column(db.String(512), nullable=True)
    status = db.Column(
        db.Enum("draft", "completed", "archived", name="resume_status"),
        nullable=False,
        default="draft",
    )
    version = db.Column(db.Integer, nullable=False, default=1)
    ats_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = db.relationship("User", back_populates="resumes")
    template = db.relationship("Template", back_populates="resumes")
    experiences = db.relationship(
        "Experience",
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="Experience.sort_order",
        lazy="selectin",
    )
    educations = db.relationship(
        "Education",
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="Education.sort_order",
        lazy="selectin",
    )
    projects = db.relationship(
        "Project",
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="Project.sort_order",
        lazy="selectin",
    )
    skills = db.relationship(
        "Skill",
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="Skill.sort_order",
        lazy="selectin",
    )
    certificates = db.relationship(
        "Certificate",
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="Certificate.sort_order",
        lazy="selectin",
    )
    languages = db.relationship(
        "Language",
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="Language.sort_order",
        lazy="selectin",
    )
    generated_pdfs = db.relationship(
        "GeneratedPDF",
        back_populates="resume",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ats_analyses = db.relationship("ATSAnalysis", back_populates="resume", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "template_id": self.template_id,
            "title": self.title,
            "target_role": self.target_role,
            "professional_summary": self.professional_summary,
            "linkedin_url": self.linkedin_url,
            "github_url": self.github_url,
            "portfolio_url": self.portfolio_url,
            "website_url": self.website_url,
            "status": self.status,
            "version": self.version,
            "ats_score": self.ats_score,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Experience(db.Model):
    __tablename__ = "experiences"

    __table_args__ = (
        db.CheckConstraint("sort_order >= 0", name="ck_experiences_sort_order_min"),
        db.CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_experiences_date_order"),
        db.Index("ix_experience_resume_sort", "resume_id", "sort_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    company = db.Column(db.String(255), nullable=False)
    job_title = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    is_current = db.Column(db.Boolean, nullable=False, default=False)
    description = db.Column(db.Text, nullable=True)
    achievements = db.Column(MutableDict.as_mutable(db.JSON), nullable=False, default=dict)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    resume = db.relationship("Resume", back_populates="experiences")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "company": self.company,
            "job_title": self.job_title,
            "location": self.location,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "start_date_display": format_month_year(self.start_date),
            "end_date_display": format_month_year(self.end_date),
            "is_current": self.is_current,
            "description": self.description,
            "achievements": self.achievements,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Education(db.Model):
    __tablename__ = "educations"

    __table_args__ = (
        db.CheckConstraint("sort_order >= 0", name="ck_educations_sort_order_min"),
        db.CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_educations_date_order"),
        db.Index("ix_education_resume_sort", "resume_id", "sort_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    institution = db.Column(db.String(255), nullable=False)
    degree = db.Column(db.String(255), nullable=True)
    field_of_study = db.Column(db.String(255), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    gpa = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    resume = db.relationship("Resume", back_populates="educations")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "institution": self.institution,
            "degree": self.degree,
            "field_of_study": self.field_of_study,
            "location": self.location,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "start_date_display": format_month_year(self.start_date),
            "end_date_display": format_month_year(self.end_date),
            "gpa": self.gpa,
            "description": self.description,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Project(db.Model):
    __tablename__ = "projects"

    __table_args__ = (
        db.CheckConstraint("sort_order >= 0", name="ck_projects_sort_order_min"),
        db.Index("ix_project_resume_sort", "resume_id", "sort_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(512), nullable=True)
    tech_stack = db.Column(MutableDict.as_mutable(db.JSON), nullable=False, default=dict)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    resume = db.relationship("Resume", back_populates="projects")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "tech_stack": self.tech_stack,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Skill(db.Model):
    __tablename__ = "skills"

    __table_args__ = (
        db.CheckConstraint("sort_order >= 0", name="ck_skills_sort_order_min"),
        db.Index("ix_skill_resume_sort", "resume_id", "sort_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(120), nullable=True)
    proficiency = db.Column(db.String(120), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    resume = db.relationship("Resume", back_populates="skills")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "name": self.name,
            "category": self.category,
            "proficiency": self.proficiency,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Certificate(db.Model):
    __tablename__ = "certificates"

    __table_args__ = (
        db.CheckConstraint("sort_order >= 0", name="ck_certificates_sort_order_min"),
        db.Index("ix_certificate_resume_sort", "resume_id", "sort_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    issuer = db.Column(db.String(255), nullable=True)
    issue_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    credential_id = db.Column(db.String(255), nullable=True)
    credential_url = db.Column(db.String(512), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    resume = db.relationship("Resume", back_populates="certificates")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "name": self.name,
            "issuer": self.issuer,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "issue_date_display": format_month_year(self.issue_date),
            "expiry_date_display": format_month_year(self.expiry_date),
            "credential_id": self.credential_id,
            "credential_url": self.credential_url,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Language(db.Model):
    __tablename__ = "languages"

    __table_args__ = (
        db.CheckConstraint("sort_order >= 0", name="ck_languages_sort_order_min"),
        db.Index("ix_language_resume_sort", "resume_id", "sort_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    proficiency = db.Column(db.String(120), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    resume = db.relationship("Resume", back_populates="languages")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "name": self.name,
            "proficiency": self.proficiency,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class GeneratedPDF(db.Model):
    __tablename__ = "generated_pdfs"

    __table_args__ = (
        db.CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_generated_pdfs_file_size_min"),
        db.Index("ix_generated_pdf_resume_generated", "resume_id", "generated_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = db.Column(db.String(512), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    checksum = db.Column(db.String(128), nullable=True)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="generated_pdfs")
    resume = db.relationship("Resume", back_populates="generated_pdfs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "resume_id": self.resume_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "checksum": self.checksum,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class JobDescription(db.Model):
    __tablename__ = "job_descriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=False)
    source_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="job_descriptions")
    analyses = db.relationship("ATSAnalysis", back_populates="job_description", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "company": self.company, "description": self.description,
                "source_url": self.source_url, "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat()}


class ATSAnalysis(db.Model):
    __tablename__ = "ats_analyses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    job_description_id = db.Column(db.Integer, db.ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    score = db.Column(db.Float, nullable=False)
    matched_keywords = db.Column(MutableDict.as_mutable(db.JSON), nullable=False, default=dict)
    missing_keywords = db.Column(MutableDict.as_mutable(db.JSON), nullable=False, default=dict)
    completeness = db.Column(MutableDict.as_mutable(db.JSON), nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    resume = db.relationship("Resume", back_populates="ats_analyses")
    job_description = db.relationship("JobDescription", back_populates="analyses")

    def to_dict(self) -> dict:
        return {"id": self.id, "resume_id": self.resume_id, "job_description_id": self.job_description_id,
                "score": self.score, "matched_keywords": self.matched_keywords, "missing_keywords": self.missing_keywords,
                "completeness": self.completeness, "created_at": self.created_at.isoformat()}
