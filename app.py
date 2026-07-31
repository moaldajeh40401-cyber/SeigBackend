from __future__ import annotations

import os

from flask import Flask, jsonify
from flask_jwt_extended.exceptions import (
	NoAuthorizationError,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import Config
from extensions import db, jwt, migrate
from routes import register_routes


def create_app(config_object: type[Config] | None = None) -> Flask:
	app = Flask(__name__)
	app.config.from_object(config_object or Config)

	db.init_app(app)
	migrate.init_app(app, db)
	jwt.init_app(app)

	register_routes(app)
	register_error_handlers(app)
	register_cli_commands(app)

	return app


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
