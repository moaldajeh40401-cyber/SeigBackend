from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import quote_plus


def build_database_uri() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        if database_url.startswith("mysql://"):
            return database_url.replace("mysql://", "mysql+pymysql://", 1)
        return database_url

    user = quote_plus(os.getenv("MYSQL_USER", "root"))
    password = quote_plus(os.getenv("MYSQL_PASSWORD", "password"))
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    database = quote_plus(os.getenv("MYSQL_DATABASE", "leon"))
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


def get_secret(name: str, development_default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    if os.getenv("FLASK_ENV", "").lower() == "production":
        raise RuntimeError(f"{name} must be set when FLASK_ENV=production")
    return development_default


class Config:
    SECRET_KEY = get_secret("SECRET_KEY", "development-only-change-this")
    JWT_SECRET_KEY = get_secret("JWT_SECRET_KEY", SECRET_KEY)
    SQLALCHEMY_DATABASE_URI = build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "280")),
    }
    JSON_SORT_KEYS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_ACCESS_TOKEN_HOURS", "24")))
