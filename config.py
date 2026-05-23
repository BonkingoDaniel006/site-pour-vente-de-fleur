import os
import secrets

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default="false"):
    return os.getenv(name, default).lower() in ("1", "true", "yes")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    FLASK_DEBUG = _env_bool("FLASK_DEBUG", "false")

    SHWARY_MERCHANT_ID = os.getenv("SHWARY_MERCHANT_ID")
    SHWARY_MERCHANT_KEY = os.getenv("SHWARY_MERCHANT_KEY")
    SHWARY_BASE_URL = os.getenv("SHWARY_BASE_URL", "https://api.shwary.com")
    CALLBACK_PATH_TOKEN = os.getenv("CALLBACK_PATH_TOKEN", "")
    SHWARY_CALLBACK_URL = os.getenv("SHWARY_CALLBACK_URL") or (
        f"http://127.0.0.1:5000/api/callback/{CALLBACK_PATH_TOKEN}"
        if CALLBACK_PATH_TOKEN
        else "http://127.0.0.1:5000/api/callback"
    )
    SHWARY_SANDBOX = _env_bool("SHWARY_SANDBOX", "true")
    USD_TO_CDF_RATE = float(os.getenv("USD_TO_CDF_RATE", "2850"))

    RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "10"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    ORDER_COOLDOWN_MINUTES = int(os.getenv("ORDER_COOLDOWN_MINUTES", "5"))

    CSRF_MAX_AGE_SECONDS = int(os.getenv("CSRF_MAX_AGE_SECONDS", "1800"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "16384"))

    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", "false")
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    # Liste d'IP autorisées pour le callback (vide = toutes). Ex: "1.2.3.4,5.6.7.8"
    CALLBACK_ALLOWED_IPS = [
        ip.strip()
        for ip in os.getenv("CALLBACK_ALLOWED_IPS", "").split(",")
        if ip.strip()
    ]


def validate_production_config():
    """Bloque le démarrage si la config prod est trop faible."""
    if Config.FLASK_DEBUG:
        return

    weak_secret = (
        not Config.SECRET_KEY
        or len(Config.SECRET_KEY) < 32
        or Config.SECRET_KEY.startswith("changez")
    )
    issues = []
    if weak_secret:
        issues.append("SECRET_KEY (min. 32 caractères aléatoires)")
    if not Config.CALLBACK_PATH_TOKEN or len(Config.CALLBACK_PATH_TOKEN) < 24:
        issues.append("CALLBACK_PATH_TOKEN (min. 24 caractères)")
    if not Config.SHWARY_MERCHANT_ID or not Config.SHWARY_MERCHANT_KEY:
        issues.append("identifiants Shwary")
    if not Config.SESSION_COOKIE_SECURE:
        issues.append("SESSION_COOKIE_SECURE=true (HTTPS requis)")
    if issues:
        raise RuntimeError(
            "Configuration production insuffisante : " + ", ".join(issues)
        )


def generate_callback_token():
    return secrets.token_urlsafe(32)
