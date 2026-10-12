"""Tests for Meta signature verification."""

import hashlib
import hmac
from app.integrations.messenger.security import verify_meta_signature


def test_verify_signature_valid():
    secret = "my_app_secret_abc"
    payload = b'{"object":"page","entry":[]}'
    h = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    header = f"sha256={h}"

    assert verify_meta_signature(payload, header, secret) is True


def test_verify_signature_invalid():
    secret = "my_app_secret_abc"
    payload = b'{"object":"page","entry":[]}'
    header = "sha256=wrong_signature_hash"

    assert verify_meta_signature(payload, header, secret) is False


def test_verify_signature_missing_header():
    assert verify_meta_signature(b"data", None, "secret") is False
    assert verify_meta_signature(b"data", "", "secret") is False


def test_verify_signature_missing_secret():
    assert verify_meta_signature(b"data", "sha256=123", "") is False


def test_verify_signature_wrong_prefix():
    assert verify_meta_signature(b"data", "sha1=12345", "secret") is False
