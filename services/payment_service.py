import requests
from config import Config


def _ensure_credentials():
    if not Config.SHWARY_MERCHANT_ID or not Config.SHWARY_MERCHANT_KEY:
        raise ValueError("Identifiants Shwary manquants")


def create_payment(phone, amount, reference_id=None, is_sandbox=None):
    """
    Crée une requête de paiement via l'API Shwary (sandbox ou production).
    """
    _ensure_credentials()

    if is_sandbox is None:
        is_sandbox = Config.SHWARY_SANDBOX

    if int(amount) <= 0:
        raise ValueError("Montant invalide")

    base_endpoint = f"{Config.SHWARY_BASE_URL.rstrip('/')}/api/v1/merchants/payment"
    country_code = "DRC"

    if is_sandbox:
        url = f"{base_endpoint}/sandbox/{country_code}"
    else:
        url = f"{base_endpoint}/{country_code}"

    headers = {
        "x-merchant-id": Config.SHWARY_MERCHANT_ID,
        "x-merchant-key": Config.SHWARY_MERCHANT_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "amount": int(amount),
        "clientPhoneNumber": phone,
        "callbackUrl": Config.SHWARY_CALLBACK_URL,
    }
    if reference_id:
        payload["referenceId"] = str(reference_id)

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=10,
        )

        if response.status_code == 401:
            return {
                "error": "Authentification échouée. Vérifiez votre Merchant ID et Secret Key.",
                "status": "failed",
            }

        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur de connexion : {str(e)}", "status": "failed"}
