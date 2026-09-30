from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from extensions import limiter
from models import User
from utils.security import hash_password, verify_password
from utils.validation import is_valid_email, is_valid_location, is_valid_phone_number

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _extract_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


@auth_bp.post("/register")
@limiter.limit("5 per hour")
def register():
    payload = _extract_payload()
    full_name = (payload.get("full_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    phone_number = (payload.get("phone_number") or "").strip() or None
    location = (payload.get("location") or "").strip() or None
    password = payload.get("password") or ""

    if not full_name or not email or not phone_number or not location or not password:
        return jsonify({"error": "validation_error", "message": "full_name, email, phone_number, location, and password are required"}), 400

    if len(full_name) < 2 or len(full_name) > 100:
        return jsonify({"error": "validation_error", "message": "full_name must be between 2 and 100 characters"}), 400

    if not is_valid_email(email):
        return jsonify({"error": "validation_error", "message": "email must be valid"}), 400

    if not is_valid_phone_number(phone_number):
        return jsonify({"error": "validation_error", "message": "phone_number must be valid"}), 400

    if not is_valid_location(location):
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
    )

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "email_taken", "message": "An account with that email already exists"}), 409

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "access_token": access_token}), 201


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