from datetime import timedelta

import pytest
from jose import jwt

from reqradar.web.api.auth import (
    ALGORITHM,
    SECRET_KEY,
    _validate_password_strength,
    create_access_token,
    hash_password,
    verify_password,
)


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("short1A", "Password must be at least 8 characters long"),
        ("password123", "Password must contain at least one uppercase letter"),
        ("PASSWORD123", "Password must contain at least one lowercase letter"),
        ("Password", "Password must contain at least one digit"),
        ("Password123", None),
    ],
)
def test_validate_password_strength(password, expected):
    assert _validate_password_strength(password) == expected


def test_hash_password_generates_verifiable_non_plaintext_hash():
    password_hash = hash_password("Password123")

    assert password_hash != "Password123"
    assert verify_password("Password123", password_hash) is True
    assert verify_password("WrongPassword123", password_hash) is False


def test_create_access_token_contains_user_subject_and_expiry():
    token = create_access_token(42, expires_delta=timedelta(minutes=5))

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "42"
    assert "exp" in payload
