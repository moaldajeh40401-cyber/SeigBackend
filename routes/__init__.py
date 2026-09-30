from __future__ import annotations

from routes.auth import auth_bp
from routes.ats import ats_bp
from routes.ai import ai_bp
from routes.health import health_bp
from routes.resume_sections import sections_bp
from routes.resumes import resumes_bp
from routes.templates import templates_bp


def register_routes(app) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ats_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(resumes_bp)
    app.register_blueprint(sections_bp)
    app.register_blueprint(templates_bp)
