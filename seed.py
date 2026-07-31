from __future__ import annotations

from typing import Any

from flask import current_app

from extensions import db
from models import Template


DEFAULT_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "classic",
        "display_name": "Classic",
        "template_path": "classic.html",
        "css_path": "static/css/templates/classic.css",
        "description": "A traditional ATS-friendly layout.",
    },
    {
        "name": "modern",
        "display_name": "Modern",
        "template_path": "classic.html",
        "css_path": "static/css/templates/modern.css",
        "description": "A clean layout with stronger section separation.",
    },
    {
        "name": "minimal",
        "display_name": "Minimal",
        "template_path": "classic.html",
        "css_path": "static/css/templates/minimal.css",
        "description": "A compact layout that keeps the focus on content.",
    },
]


def seed_default_templates() -> None:
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        from app import create_app

        app = create_app()

    with app.app_context():
        for template_data in DEFAULT_TEMPLATES:
            template = Template.query.filter_by(name=template_data["name"]).first()
            if template is None:
                template = Template(**template_data)
                db.session.add(template)
            else:
                template.display_name = template_data["display_name"]
                template.template_path = template_data["template_path"]
                template.css_path = template_data["css_path"]
                template.description = template_data["description"]
                template.is_active = True

        db.session.commit()


if __name__ == "__main__":
    seed_default_templates()
