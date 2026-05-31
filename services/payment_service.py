from shwary import (
    AuthenticationError,
    InsufficientFundsError,
    RateLimitingError,
    Shwary,
    ShwaryAPIError,
    ValidationError,
)

from config import Config

_client = None


def _ensure_credentials():
    if not Config.SHWARY_MERCHANT_ID or not Config.SHWARY_MERCHANT_KEY:
        raise ValueError("Identifiants Shwary manquants")


def get_shwary_client():
    global _client
    _ensure_credentials()
    if _client is None:
        _client = Shwary(
            merchant_id=Config.SHWARY_MERCHANT_ID,
            merchant_key=Config.SHWARY_MERCHANT_KEY,
            is_sandbox=Config.SHWARY_SANDBOX,
        )
    return _client


def close_shwary_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None


def create_payment(phone, amount, reference_id=None, is_sandbox=None):
    """
    Initie un paiement via le SDK officiel shwary-python.
    reference_id est conservé pour compatibilité (lien commande via shwary_tx_id).
    """
    del reference_id, is_sandbox  # le SDK ne prend pas referenceId ; lien via tx id

    client = get_shwary_client()
    payment = client.initiate_payment(
        country="DRC",
        amount=float(amount),
        phone_number=phone,
        callback_url=Config.SHWARY_CALLBACK_URL,
    )
    return payment.model_dump()


def verify_transaction(tx_id, expected_status, expected_amount):
    """
    Confirme un webhook en interrogeant directement l'API Shwary.
    """
    client = get_shwary_client()
    tx = client.get_transaction(tx_id)
    if tx.status != expected_status:
        return False
    if int(tx.amount) != int(expected_amount):
        return False
    return True


__all__ = [
    "AuthenticationError",
    "InsufficientFundsError",
    "RateLimitingError",
    "ShwaryAPIError",
    "ValidationError",
    "close_shwary_client",
    "create_payment",
    "get_shwary_client",
    "verify_transaction",
]
