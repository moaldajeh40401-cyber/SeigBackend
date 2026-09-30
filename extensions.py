from __future__ import annotations

import flask_sqlalchemy as flask_sqlalchemy_module
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

try:
	from flask_migrate import Migrate
except ModuleNotFoundError:
	class Migrate:  # type: ignore[override]
		def init_app(self, app, db):
			return None


_app_ctx_stack = getattr(flask_sqlalchemy_module, "_app_ctx_stack", None)
if _app_ctx_stack is not None and not hasattr(_app_ctx_stack, "__ident_func__"):
	def _scopefunc():
		top = getattr(_app_ctx_stack, "top", None)
		return id(top) if top is not None else 0

	setattr(_app_ctx_stack, "__ident_func__", _scopefunc)

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=[])