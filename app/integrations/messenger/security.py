"""Security utilities for Meta Messenger webhooks.

Implements HMAC-SHA256 signature verification against X-Hub-Signature-256 header.
"""

import hmac
import hashlib
from app.core.logging import get_logger

logger = get_logger(__name__)


def verify_meta_signature(payload_bytes: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Verify that incoming request payload was signed by Meta using META_APP_SECRET.

    Args:
        payload_bytes: Raw HTTP request body bytes.
        signature_header: Content of X-Hub-Signature-256 header (format: sha256=<signature>).
        app_secret: Meta application secret key.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature_header or not app_secret:
        logger.warning("Missing signature header or app secret for verification")
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        logger.warning("Invalid signature header format: missing sha256= prefix")
        return False

    expected_hash = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    expected_header = f"{prefix}{expected_hash}"
    is_valid = hmac.compare_digest(expected_header, signature_header)

    if not is_valid:
        logger.warning("Meta webhook signature verification failed")

    return is_valid
