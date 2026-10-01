from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, redirect, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from extensions import db
from extensions import limiter
from models import User
from utils.security import hash_password, verify_password
from utils.validation import is_valid_email, is_valid_location, is_valid_phone_number

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _extract_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _verification_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="seig-email-verification")


def _send_verification_email(user: User) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_username or "")
    if not smtp_host or not smtp_username or not smtp_password or not smtp_from:
        raise RuntimeError("SMTP email settings are not configured")

    token = _verification_serializer().dumps({"user_id": user.id, "email": user.email})
    frontend_url = os.getenv("FRONTEND_URLS", "http://localhost:5173").split(",")[0].strip().rstrip("/")
    verification_url = f"{frontend_url}/?verify_token={quote(token)}"
    message = EmailMessage()
    message["Subject"] = "Verify your Seig account"
    message["From"] = smtp_from
    message["To"] = user.email
    message.set_content(f"Verify your Seig account within 24 hours:\n\n{verification_url}\n")
    with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as smtp:
        smtp.starttls()
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)


@auth_bp.post("/register")
@limiter.limit("5 per hour")
def register():
    payload = _extract_payload()
    full_name = (payload.get("full_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    phone_number = (payload.get("phone_number") or "").strip() or None
    location = (payload.get("location") or "").strip() or None
    password = payload.get("password") or ""

    if not full_name or not email or not phone_number or not password:
        return jsonify({"error": "validation_error", "message": "full_name, email, phone_number, and password are required"}), 400

    if len(full_name) < 2 or len(full_name) > 100:
        return jsonify({"error": "validation_error", "message": "full_name must be between 2 and 100 characters"}), 400

    if not is_valid_email(email):
        return jsonify({"error": "validation_error", "message": "email must be valid"}), 400

    if not is_valid_phone_number(phone_number):
        return jsonify({"error": "validation_error", "message": "phone_number must be valid"}), 400

    if location and not is_valid_location(location):
        return jsonify({"error": "validation_error", "message": "location must be valid"}), 400

    if len(password) < 8:
        return jsonify({"error": "validation_error", "message": "password must be at least 8 characters long"}), 400

    if User.query.filter_by(email=email).first() is not None:
        return jsonify({"error": "email_taken", "message": "An account with that email already exists"}), 409

    user = User(
        full_name=full_name,
        email=email,
        phone_number=phone_number,
        location=location,
        password_hash=hash_password(password),
        is_email_verified=False,
    )

    try:
        db.session.add(user)
        db.session.commit()
        _send_verification_email(user)
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "email_taken", "message": "An account with that email already exists"}), 409
    except RuntimeError as error:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"error": "email_unavailable", "message": str(error)}), 503

    return jsonify({"user": user.to_dict(), "verification_required": True, "message": "Check your email to verify your account before signing in."}), 201


@auth_bp.post("/login")
@limiter.limit("10 per minute")
def login():
    payload = _extract_payload()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"error": "validation_error", "message": "email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not verify_password(password, user.password_hash):
        return jsonify({"error": "invalid_credentials", "message": "Invalid email or password"}), 401
    if not user.is_email_verified:
        return jsonify({"error": "email_not_verified", "message": "Verify your email address before signing in"}), 403

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "access_token": access_token})


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    return jsonify({"user": user.to_dict()})


@auth_bp.get("/verify-email")
def verify_email():
    token = request.args.get("token", "")
    try:
        data = _verification_serializer().loads(token, max_age=86400)
        user = db.session.get(User, int(data["user_id"]))
        if user is None or user.email != data["email"]:
            raise BadSignature
        user.is_email_verified = True
        db.session.commit()
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return jsonify({"error": "invalid_verification", "message": "This verification link is invalid or expired"}), 400

    frontend_url = os.getenv("FRONTEND_URLS", "http://localhost:5173").split(",")[0].strip().rstrip("/")
    return redirect(f"{frontend_url}/?verified=1")