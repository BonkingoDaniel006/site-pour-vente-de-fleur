import re
import secrets
import time
from collections import defaultdict

from flask import session

from config import Config

PHONE_DRC_PATTERN = re.compile(r"^\+243\d{9}$")
PRODUCT_ID_PATTERN = re.compile(r"^[a-z0-9_]{2,40}$")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_rate_buckets = defaultdict(list)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


def ensure_secret_key(app):
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY manquant dans la configuration.")


def apply_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response


def generate_csrf_token():
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    session["csrf_created_at"] = time.time()
    return token


def validate_csrf_token(token):
    expected = session.get("csrf_token")
    created_at = session.get("csrf_created_at", 0)
    if not token or not expected:
        return False
    if time.time() - created_at > Config.CSRF_MAX_AGE_SECONDS:
        return False
    return secrets.compare_digest(expected, token)


def validate_phone_drc(phone):
    if not phone:
        return False
    normalized = phone.strip().replace(" ", "")
    return bool(PHONE_DRC_PATTERN.match(normalized))


def normalize_phone_drc(phone):
    return phone.strip().replace(" ", "")


def validate_product_id(product_id):
    return bool(product_id and PRODUCT_ID_PATTERN.match(product_id))


def sanitize_text(value, max_length):
    if value is None:
        return ""
    cleaned = CONTROL_CHARS.sub("", str(value)).strip()
    return cleaned[:max_length]


def is_honeypot_triggered(value):
    return bool(value and value.strip())


def check_rate_limit(key, max_requests=None, window_seconds=None):
    max_requests = max_requests or Config.RATE_LIMIT_MAX
    window_seconds = window_seconds or Config.RATE_LIMIT_WINDOW
    now = time.time()
    bucket = _rate_buckets[key]
    _rate_buckets[key] = [t for t in bucket if now - t < window_seconds]
    if len(_rate_buckets[key]) >= max_requests:
        return False
    _rate_buckets[key].append(now)
    return True


def is_callback_ip_allowed(client_ip):
    if not Config.CALLBACK_ALLOWED_IPS:
        return True
    return client_ip in Config.CALLBACK_ALLOWED_IPS


def verify_shwary_callback(data):
    """
    Vérifie le callback Shwary (pas de signature HMAC documentée).
    Couches : marchand, sandbox, devise, commande, montant, anti-rejeu.
    """
    if not isinstance(data, dict):
        return None, "payload invalide"

    merchant_id = data.get("userId")
    if merchant_id != Config.SHWARY_MERCHANT_ID:
        return None, "marchand non reconnu"

    tx_id = data.get("id")
    status = data.get("status")
    amount = data.get("amount")
    reference_id = data.get("referenceId")
    currency = (data.get("currency") or "").upper()
    is_sandbox = data.get("isSandbox")

    if not tx_id or status is None or amount is None:
        return None, "champs requis manquants"

    if currency and currency != "CDF":
        return None, "devise invalide"

    if is_sandbox is not None and bool(is_sandbox) != Config.SHWARY_SANDBOX:
        return None, "mode sandbox incohérent"

    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return None, "montant invalide"

    from services.orders import (
        get_order_by_id,
        get_order_by_shwary_tx,
        is_webhook_duplicate,
        record_webhook_event,
    )

    order = None
    if reference_id:
        order = get_order_by_id(str(reference_id))
    if not order:
        order = get_order_by_shwary_tx(str(tx_id))
    if not order:
        return None, "commande introuvable"

    if order["amount_cdf"] != amount:
        return None, "montant incohérent"

    event_key = f"{tx_id}:{status}"
    if is_webhook_duplicate(event_key):
        return order, "duplicate"

    record_webhook_event(event_key, tx_id, status)
    return order, None
