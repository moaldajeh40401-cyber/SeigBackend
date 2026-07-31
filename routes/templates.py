from __future__ import annotations

import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Template

templates_bp = Blueprint("templates", __name__, url_prefix="/api/templates")

BUILT_IN_TEMPLATE_PATH = "classic.html"


def _is_admin() -> bool:
    """Template definitions are application configuration, not user content."""
    allowed_emails = {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }
    if not allowed_emails:
        return False
    from models import User
    user = db.session.get(User, int(get_jwt_identity()))
    return user is not None and user.email.lower() in allowed_emails


def _admin_or_403():
    if not _is_admin():
        return jsonify({"error": "forbidden", "message": "Administrator access is required"}), 403
    return None


def _extract_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _normalize_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    value = str(value).strip()
    return value or None


def _normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _require_template(template_id: int) -> Template | None:
    return db.session.get(Template, template_id)


@templates_bp.get("")
def list_templates():
    include_inactive = request.args.get("include_inactive", "false").lower() in {"1", "true", "yes"}
    query = Template.query
    if not include_inactive:
        query = query.filter_by(is_active=True)

    templates = query.order_by(Template.name.asc()).all()
    return jsonify({"items": [template.to_dict() for template in templates]})


@templates_bp.post("")
@jwt_required()
def create_template():
    admin_error = _admin_or_403()
    if admin_error is not None:
        return admin_error
    payload = _extract_payload()
    name = _normalize_string(payload.get("name"))
    display_name = _normalize_string(payload.get("display_name"))
    template_path = _normalize_string(payload.get("template_path"))
    if not name or not display_name or not template_path:
        return jsonify({"error": "validation_error", "message": "name, display_name, and template_path are required"}), 400
    if template_path != BUILT_IN_TEMPLATE_PATH:
        return jsonify({"error": "validation_error", "message": "template_path must use the built-in resume layout"}), 400

    template = Template(
        name=name,
        display_name=display_name,
        template_path=template_path,
        css_path=_normalize_string(payload.get("css_path")),
        description=_normalize_string(payload.get("description")),
        is_active=_normalize_bool(payload.get("is_active", True)),
    )

    try:
        db.session.add(template)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "conflict", "message": "Template name must be unique"}), 409

    return jsonify({"template": template.to_dict()}), 201


@templates_bp.get("/<int:template_id>")
def get_template(template_id: int):
    template = _require_template(template_id)
    if template is None:
        return jsonify({"error": "not_found", "message": "Template not found"}), 404
    return jsonify({"template": template.to_dict()})


@templates_bp.patch("/<int:template_id>")
@jwt_required()
def update_template(template_id: int):
    admin_error = _admin_or_403()
    if admin_error is not None:
        return admin_error
    template = _require_template(template_id)
    if template is None:
        return jsonify({"error": "not_found", "message": "Template not found"}), 404

    payload = _extract_payload()
    if "name" in payload:
        name = _normalize_string(payload.get("name"))
        if not name:
            return jsonify({"error": "validation_error", "message": "name cannot be empty"}), 400
        template.name = name

    if "display_name" in payload:
        display_name = _normalize_string(payload.get("display_name"))
        if not display_name:
            return jsonify({"error": "validation_error", "message": "display_name cannot be empty"}), 400
        template.display_name = display_name

    if "template_path" in payload:
        template_path = _normalize_string(payload.get("template_path"))
        if not template_path:
            return jsonify({"error": "validation_error", "message": "template_path cannot be empty"}), 400
        if template_path != BUILT_IN_TEMPLATE_PATH:
            return jsonify({"error": "validation_error", "message": "template_path must use the built-in resume layout"}), 400
        template.template_path = template_path

    if "css_path" in payload:
        template.css_path = _normalize_string(payload.get("css_path"))

    if "description" in payload:
        template.description = _normalize_string(payload.get("description"))

    if "is_active" in payload:
        template.is_active = _normalize_bool(payload.get("is_active"))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "conflict", "message": "Template name must be unique"}), 409

    return jsonify({"template": template.to_dict()})


@templates_bp.delete("/<int:template_id>")
@jwt_required()
def delete_template(template_id: int):
    admin_error = _admin_or_403()
    if admin_error is not None:
        return admin_error
    template = _require_template(template_id)
    if template is None:
        return jsonify({"error": "not_found", "message": "Template not found"}), 404

    db.session.delete(template)
    db.session.commit()
    return jsonify({"deleted": True, "template_id": template_id})
