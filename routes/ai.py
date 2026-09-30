from __future__ import annotations

import json
import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from openai import OpenAI

from extensions import limiter

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

SYSTEM_PROMPT = """
You are an ATS resume editor. Rewrite the supplied resume bullet using the Google XYZ formula:
Accomplished [X], measured by [Y], by doing [Z]. Start with a strong past-tense action verb.
Strip first-person and personal pronouns. Preserve the factual meaning and do not invent claims.
When a metric is absent, insert a concise bracketed placeholder such as [X%], [$X], or [N].
Return only valid JSON with this exact shape:
{
  "suggestions": [
    {"id": 1, "text": "...", "keywords": ["..."], "focus": "Impact"},
    {"id": 2, "text": "...", "keywords": ["..."], "focus": "Technical"}
  ]
}
Return exactly two useful alternatives. Keep each suggestion to one resume bullet.
""".strip()


@ai_bp.post("/enhance-bullet")
@jwt_required()
@limiter.limit("10 per minute")
def enhance_bullet():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("bullet"), str):
        return jsonify({"error": "validation_error", "message": "bullet must be a string"}), 400

    bullet = payload["bullet"].strip()
    if not bullet:
        return jsonify({"error": "validation_error", "message": "bullet cannot be empty"}), 400
    if len(bullet) > 2000:
        return jsonify({"error": "validation_error", "message": "bullet must be 2000 characters or fewer"}), 400

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return jsonify({"error": "ai_unavailable", "message": "OPENROUTER_API_KEY is not configured"}), 503

    job_title = payload.get("job_title") if isinstance(payload.get("job_title"), str) else ""
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    try:
        completion = client.chat.completions.create(
            model="qwen/qwen-2.5-72b-instruct",
            temperature=0.35,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"bullet": bullet, "job_title": job_title})},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        result = json.loads(content)
        suggestions = result.get("suggestions") if isinstance(result, dict) else None
        if not isinstance(suggestions, list):
            raise ValueError("Model response did not contain suggestions")

        normalized = []
        for index, suggestion in enumerate(suggestions[:2], start=1):
            if not isinstance(suggestion, dict) or not isinstance(suggestion.get("text"), str):
                continue
            keywords = suggestion.get("keywords", [])
            normalized.append({
                "id": index,
                "text": suggestion["text"].strip(),
                "keywords": [str(keyword) for keyword in keywords] if isinstance(keywords, list) else [],
                "focus": str(suggestion.get("focus") or ("Impact" if index == 1 else "Technical")),
            })
        if len(normalized) < 2:
            raise ValueError("Model response did not contain two valid suggestions")
        return jsonify({"suggestions": normalized})
    except (ValueError, json.JSONDecodeError) as error:
        return jsonify({"error": "ai_invalid_response", "message": str(error)}), 502
    except Exception:
        return jsonify({"error": "ai_request_failed", "message": "The AI provider could not enhance this bullet"}), 502