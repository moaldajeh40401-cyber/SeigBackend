from __future__ import annotations

import re
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[0-9+()\-\s.]{7,25}$")
URL_RE = re.compile(r"^(https?://)?([A-Za-z0-9-]+\.)+[A-Za-z]{2,}(/.*)?$", re.IGNORECASE)


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value.strip()))


def is_valid_phone_number(value: str) -> bool:
    candidate = value.strip()
    if not PHONE_RE.match(candidate):
        return False
    digit_count = sum(character.isdigit() for character in candidate)
    return 7 <= digit_count <= 15


def is_valid_location(value: str) -> bool:
    return 2 <= len(value.strip()) <= 255


def normalize_url(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return candidate
    if candidate.startswith(("http://", "https://")):
        return candidate
    return f"https://{candidate}"


def is_valid_url(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    if not URL_RE.match(candidate):
        return False
    parsed = urlparse(normalize_url(candidate))
    return bool(parsed.scheme and parsed.netloc)


def count_words(value: str) -> int:
    return len([part for part in value.strip().split() if part])


def contains_first_person_pronoun(value: str) -> bool:
    lowered = f" {value.lower()} "
    return any(token in lowered for token in (" i ", " me ", " my ", " i'm ", " i've ", " ive ", " myself "))