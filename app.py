import logging
import secrets

from flask import Flask, abort, jsonify, render_template, request

from catalog import get_product, list_products, product_amount_cdf, product_price_label
from config import Config, validate_production_config
from services.orders import (
    attach_shwary_transaction,
    create_order,
    has_recent_pending_order,
    init_db,
    update_order_status,
)
from services.payment_service import create_payment
from services.security import (
    apply_security_headers,
    check_rate_limit,
    ensure_secret_key,
    generate_csrf_token,
    is_callback_ip_allowed,
    is_honeypot_triggered,
    normalize_phone_drc,
    sanitize_text,
    validate_csrf_token,
    validate_phone_drc,
    validate_product_id,
    verify_shwary_callback,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=Config.SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE=Config.SESSION_COOKIE_SECURE,
)

if not app.config["SECRET_KEY"]:
    app.config["SECRET_KEY"] = secrets.token_hex(32)
    logger.warning(
        "SECRET_KEY non défini dans .env — clé temporaire (sessions invalidées au redémarrage)."
    )

ensure_secret_key(app)
validate_production_config()
init_db()


def client_ip():
    if Config.CALLBACK_ALLOWED_IPS and request.path.startswith("/api/callback"):
        return request.remote_addr or "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


@app.after_request
def set_security_headers(response):
    return apply_security_headers(response)


@app.route("/")
def home():
    return render_template("index.html", products=list_products())


@app.route("/paiement")
def paiement():
    product_id = request.args.get("produit_id", "")
    if not validate_product_id(product_id):
        abort(404)

    product = get_product(product_id)
    if not product:
        abort(404)

    amount_cdf = product_amount_cdf(product)
    return render_template(
        "paiement.html",
        produit=product["name"],
        produit_id=product_id,
        prix_label=product_price_label(product),
        amount_cdf=amount_cdf,
        sandbox=Config.SHWARY_SANDBOX,
        csrf_token=generate_csrf_token(),
    )


@app.route("/pay", methods=["POST"])
def pay():
    if not check_rate_limit(f"pay:{client_ip()}"):
        return jsonify({"error": "Trop de tentatives. Réessayez plus tard."}), 429

    if not validate_csrf_token(request.form.get("csrf_token")):
        return jsonify({"error": "Session expirée. Rechargez la page."}), 403

    if is_honeypot_triggered(request.form.get("website")):
        logger.warning("Soumission bloquée (honeypot) depuis %s", client_ip())
        return jsonify({"error": "Requête refusée."}), 400

    product_id = request.form.get("produit_id", "")
    if not validate_product_id(product_id):
        return jsonify({"error": "Produit invalide."}), 400

    product = get_product(product_id)
    if not product:
        return jsonify({"error": "Produit invalide."}), 400

    phone = request.form.get("phone", "")
    customer_name = sanitize_text(request.form.get("name"), 120)
    address = sanitize_text(request.form.get("address"), 255)

    if not customer_name or not address:
        return jsonify({"error": "Nom et adresse requis."}), 400

    if not validate_phone_drc(phone):
        return jsonify({"error": "Numéro invalide. Format attendu : +243XXXXXXXXX"}), 400

    phone = normalize_phone_drc(phone)

    if has_recent_pending_order(phone, product_id, Config.ORDER_COOLDOWN_MINUTES):
        return jsonify(
            {
                "error": (
                    f"Une commande est déjà en cours pour ce numéro. "
                    f"Attendez {Config.ORDER_COOLDOWN_MINUTES} minutes."
                )
            }
        ), 429

    amount_cdf = product_amount_cdf(product)

    order_id = create_order(
        product_id=product_id,
        product_name=product["name"],
        amount_cdf=amount_cdf,
        phone=phone,
        customer_name=customer_name,
        address=address,
    )

    try:
        result = create_payment(phone, amount_cdf, reference_id=order_id)
    except ValueError:
        return jsonify({"error": "Configuration paiement incomplète."}), 503
    except Exception:
        logger.exception("Erreur lors de l'appel Shwary")
        return jsonify({"error": "Paiement indisponible. Réessayez."}), 500

    if result.get("error"):
        return jsonify({"error": result["error"]}), 400

    shwary_tx_id = result.get("id")
    if shwary_tx_id:
        attach_shwary_transaction(order_id, shwary_tx_id)

    safe_result = {
        "status": result.get("status"),
        "id": shwary_tx_id,
    }
    return jsonify(safe_result)


def _handle_payment_callback():
    if not check_rate_limit(f"callback:{client_ip()}", max_requests=30):
        return jsonify({"error": "too many requests"}), 429

    if not is_callback_ip_allowed(client_ip()):
        logger.warning("Callback refusé (IP): %s", client_ip())
        return jsonify({"error": "forbidden"}), 403

    if not request.is_json:
        return jsonify({"error": "invalid content type"}), 400

    data = request.get_json(silent=True)
    order, error = verify_shwary_callback(data)
    if error == "duplicate":
        return jsonify({"status": "already_processed"}), 200
    if error:
        logger.warning("Callback Shwary rejeté : %s", error)
        return jsonify({"error": "rejected"}), 400

    status = data.get("status")
    order_id = order["id"]
    if status in ("completed", "success"):
        update_order_status(order_id, "paid", expected_amount=data.get("amount"))
        logger.info("Commande %s payée", order_id[:8])
    elif status == "failed":
        update_order_status(order_id, "failed", expected_amount=data.get("amount"))
        logger.info("Commande %s échouée", order_id[:8])
    else:
        update_order_status(order_id, status or "pending", expected_amount=data.get("amount"))

    return jsonify({"status": "received"}), 200


@app.route("/api/callback", methods=["POST"])
def payment_callback_legacy():
    if Config.CALLBACK_PATH_TOKEN:
        return jsonify({"error": "not found"}), 404
    return _handle_payment_callback()


@app.route("/api/callback/<token>", methods=["POST"])
def payment_callback_secure(token):
    if not Config.CALLBACK_PATH_TOKEN:
        return jsonify({"error": "not configured"}), 404
    if not secrets.compare_digest(token, Config.CALLBACK_PATH_TOKEN):
        return jsonify({"error": "not found"}), 404
    return _handle_payment_callback()


if __name__ == "__main__":
    app.run(debug=Config.FLASK_DEBUG, host="127.0.0.1", port=5000)
