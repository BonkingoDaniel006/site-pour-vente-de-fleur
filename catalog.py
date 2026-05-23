from config import Config


PRODUCTS = {
    "rose_rouge": {
        "name": "Rose Rouge",
        "image": "uploads/Roserouge.jpg",
        "price_usd": 20,
    },
    "tulipe_bleu": {
        "name": "tulipe bleu",
        "image": "uploads/Tulipebleu.jpg",
        "price_usd": 35,
    },
    "petite_marguerite": {
        "name": "Petite marguerite",
        "image": "uploads/Petitefleur.jpg",
        "price_cdf": 250,
    },
}


def get_product(product_id):
    return PRODUCTS.get(product_id)


def product_amount_cdf(product):
    if "price_cdf" in product:
        return int(product["price_cdf"])
    return int(product["price_usd"] * Config.USD_TO_CDF_RATE)


def product_price_label(product):
    if "price_cdf" in product:
        return f"{product['price_cdf']} FC"
    amount_cdf = product_amount_cdf(product)
    return f"{product['price_usd']}$ (≈ {amount_cdf} CDF)"


def list_products():
    items = []
    for product_id, product in PRODUCTS.items():
        items.append(
            {
                "id": product_id,
                "name": product["name"],
                "image": product["image"],
                "price_label": product_price_label(product),
            }
        )
    return items
