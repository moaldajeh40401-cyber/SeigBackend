from __future__ import annotations

import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter.errors import RateLimitExceeded
from flask_jwt_extended.exceptions import (
	NoAuthorizationError,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import Config
from extensions import db, jwt, limiter, migrate
from routes import register_routes


def create_app(config_object: type[Config] | None = None) -> Flask:
	app = Flask(__name__)
	app.config.from_object(config_object or Config)
	allowed_origins = {
		origin.strip().rstrip("/")
		for origin in os.getenv("FRONTEND_URLS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
		if origin.strip()
	}
	CORS(app, resources={r"/api/*": {"origins": list(allowed_origins)}}, allow_headers=["Content-Type", "Authorization"], methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"])

	db.init_app(app)
	migrate.init_app(app, db)
	jwt.init_app(app)
	limiter.init_app(app)

	register_routes(app)
	register_error_handlers(app)
	register_cli_commands(app)
	register_security_headers(app)

	return app


def register_security_headers(app: Flask) -> None:
	@app.after_request
	def add_security_headers(response):
		response.headers.setdefault("X-Content-Type-Options", "nosniff")
		response.headers.setdefault("X-Frame-Options", "DENY")
		response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
		response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
		if os.getenv("FLASK_ENV", "").lower() == "production":
			response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		return response


def register_cli_commands(app: Flask) -> None:
	from seed import seed_default_templates

	@app.cli.command("seed-templates")
	def seed_templates_command() -> None:
		seed_default_templates()


def register_error_handlers(app: Flask) -> None:
	@app.errorhandler(400)
	def bad_request(error):
		description = getattr(error, "description", "Bad request")
		return jsonify({"error": "bad_request", "message": description}), 400

	@app.errorhandler(404)
	def not_found(error):
		description = getattr(error, "description", "Resource not found")
		return jsonify({"error": "not_found", "message": description}), 404

	@app.errorhandler(405)
	def method_not_allowed(error):
		return jsonify({"error": "method_not_allowed", "message": "Method not allowed"}), 405

	@app.errorhandler(IntegrityError)
	def handle_integrity_error(error):
		db.session.rollback()
		return jsonify({"error": "integrity_error", "message": "Database constraint violated"}), 409

	@app.errorhandler(SQLAlchemyError)
	def handle_database_error(error):
		db.session.rollback()
		return jsonify({"error": "database_error", "message": "Database operation failed"}), 500

	@app.errorhandler(NoAuthorizationError)
	def handle_missing_token(error):
		return jsonify({"error": "authorization_required", "message": str(error)}), 401

	@app.errorhandler(413)
	def request_too_large(error):
		return jsonify({"error": "payload_too_large", "message": "Request body is too large"}), 413

	@app.errorhandler(RateLimitExceeded)
	def rate_limit_exceeded(error):
		return jsonify({"error": "rate_limit_exceeded", "message": "Too many requests. Please try again later."}), 429

	@jwt.unauthorized_loader
	def handle_jwt_missing(reason: str):
		return jsonify({"error": "authorization_required", "message": reason}), 401

	@jwt.invalid_token_loader
	def handle_jwt_invalid(reason: str):
		return jsonify({"error": "invalid_token", "message": reason}), 401


app = create_app()


if __name__ == "__main__":
	app.run(
		host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),
		port=int(os.getenv("PORT", "5000")),
		debug=os.getenv("FLASK_DEBUG", "0") == "1",
	)
