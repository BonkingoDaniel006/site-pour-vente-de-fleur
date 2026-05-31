# Site pour Vente de Fleurs

**Plantes Ornementales — Made in DRC**

Application web Flask pour la vente de fleurs avec paiement Mobile Money via [Shwary](https://shwary.com) (RDC).

> Ce dépôt a évolué d'un site HTML statique vers une application Flask complète avec paiement sécurisé. Ce README documente l'état actuel du projet, les modifications apportées, la sécurité et les étapes pour une mise en production.

---

## Sommaire

1. [État du projet](#état-du-projet)
2. [Changements par rapport au code de base](#changements-par-rapport-au-code-de-base)
3. [Structure du projet](#structure-du-projet)
4. [Intégration Shwary (paiement)](#intégration-shwary-paiement)
5. [Sécurité](#sécurité)
6. [Installation et lancement](#installation-et-lancement)
7. [Configuration (`.env`)](#configuration-env)
8. [Ce qui manque encore](#ce-qui-manque-encore)
9. [Checklist production](#checklist-production)
10. [Parcours utilisateur](#parcours-utilisateur)

---

## État du projet

| Fonctionnalité | Statut |
|----------------|--------|
| Catalogue de produits (serveur) | ✅ |
| Page de paiement + livraison | ✅ |
| Paiement Mobile Money (Shwary SDK) | ✅ |
| Webhooks / callbacks | ✅ |
| Commandes en base SQLite | ✅ |
| Sécurisation (CSRF, rate limit, etc.) | ✅ |
| Barre de recherche | 🚧 (UI seulement, non fonctionnelle) |
| Panier (`cart.html`, `checkout.html`) | 🚧 (templates orphelins) |
| Images produits | ⚠️ (`static/uploads/` à compléter) |
| Back-office / admin | ❌ |
| HTTPS / hébergement prod | ❌ (à faire) |

---

## Changements par rapport au code de base

### Code original

Le projet initial était un **site HTML/CSS statique** :
- Ouverture de `index.html` directement dans le navigateur
- Liens de commande avec prix dans l'URL (`?prix=20`)
- Placeholder « insérer API de paiement » dans `paiement.html`
- `app.py` minimal avec import `mysql.connector` inutilisé (bloquant au démarrage)
- Pas de gestion de commandes ni de backend réel

### Modifications effectuées

#### Backend Flask

- **`app.py`** : application complète avec routes `/`, `/paiement`, `/pay`, `/api/callback/<token>`
- **`config.py`** : configuration centralisée via variables d'environnement
- **`catalog.py`** : catalogue produits côté serveur (prix jamais fiables depuis le client)
- **`services/payment_service.py`** : intégration du SDK officiel `shwary-python`
- **`services/orders.py`** : persistance des commandes (SQLite)
- **`services/security.py`** : CSRF, rate limiting, validation webhooks, en-têtes HTTP

#### Frontend

- **`templates/index.html`** : catalogue dynamique depuis `catalog.py` (liens `produit_id`)
- **`templates/paiement.html`** : formulaire livraison + paiement Shwary (fetch AJAX vers `/pay`)
- **`static/style.css`** : styles checkout, statuts paiement, honeypot

#### Configuration et dépendances

- **`.env`** / **`.env.example`** : secrets Shwary, clés Flask, mode sandbox
- **`requirements.txt`** : `Flask`, `python-dotenv`, `shwary-python`
- **`.gitignore`** : exclusion de `.env`, `data/`, `logs/`

#### Produits

| ID | Nom | Prix |
|----|-----|------|
| `rose_rouge` | Rose Rouge | 20 $ (≈ 57 000 CDF) |
| `tulipe_bleu` | tulipe bleu | 35 $ (≈ 99 750 CDF) |
| `petite_marguerite` | Petite marguerite | 2 900 CDF |

> **Note :** Shwary impose un minimum de **2 900 CDF** en RDC. La Petite marguerite était initialement à 250 FC ; le prix a été ajusté pour respecter cette contrainte API.

---

## Structure du projet

```
site-pour-vente-de-fleur/
├── app.py                  # Point d'entrée Flask
├── config.py               # Configuration (.env)
├── catalog.py              # Catalogue produits (source de vérité des prix)
├── requirements.txt
├── .env.example            # Modèle de configuration (sans secrets)
├── data/
│   └── orders.db           # Base SQLite (générée au 1er lancement)
├── services/
│   ├── payment_service.py  # Client Shwary (SDK)
│   ├── orders.py           # CRUD commandes + anti-rejeu webhooks
│   └── security.py         # CSRF, rate limit, validation callback
├── static/
│   ├── style.css
│   └── uploads/            # Images produits (à ajouter)
├── templates/
│   ├── index.html
│   ├── paiement.html
│   ├── cart.html           # Non utilisé
│   └── checkout.html       # Non utilisé
└── logs/
    └── shwary.log          # Logs SDK Shwary
```

---

## Intégration Shwary (paiement)

### SDK utilisé

Nous utilisons le SDK officiel **[shwary-python](https://pypi.org/project/shwary-python/)** (mode synchrone, adapté à Flask).

Documentation SDK complète : voir `README_SHWARY.md` dans ce dépôt.

### Flux de paiement

```
1. Client → Accueil → « Commander » (produit_id)
2. Client → /paiement?produit_id=rose_rouge
3. Client remplit nom, adresse, téléphone (+243…)
4. POST /pay (CSRF + produit_id + données livraison)
5. Serveur :
   - Recalcule le montant depuis catalog.py
   - Crée une commande en base (status: pending)
   - Appelle Shwary : client.initiate_payment(...)
   - Enregistre shwary_tx_id sur la commande
6. Client reçoit status "pending" → validation USSD sur le téléphone
7. Shwary → POST /api/callback/<token> (notification de statut)
8. Serveur :
   - Valide le payload (WebhookPayload)
   - Vérifie marchand, montant, commande
   - Confirme via API : get_transaction(id)
   - Met à jour la commande (paid / failed)
```

### Fichiers clés

**`services/payment_service.py`**

```python
from shwary import Shwary

client = Shwary(
    merchant_id=Config.SHWARY_MERCHANT_ID,
    merchant_key=Config.SHWARY_MERCHANT_KEY,
    is_sandbox=Config.SHWARY_SANDBOX,
)
payment = client.initiate_payment(
    country="DRC",
    amount=amount_cdf,
    phone_number=phone,
    callback_url=Config.SHWARY_CALLBACK_URL,
)
```

**Exceptions gérées dans `app.py` :**

- `ValidationError` — numéro ou montant invalide
- `AuthenticationError` — identifiants Shwary incorrects
- `InsufficientFundsError` — solde marchand insuffisant
- `RateLimitingError` — trop de requêtes vers Shwary
- `ShwaryAPIError` — autres erreurs API

### Webhooks

Shwary **ne documente pas de signature HMAC** sur les callbacks. Notre stratégie :

1. URL callback avec **token secret** (`/api/callback/<CALLBACK_PATH_TOKEN>`)
2. Validation du payload avec `WebhookPayload` (Pydantic)
3. Vérification `userId` = notre marchand
4. Correspondance commande locale + montant
5. **Double confirmation** via `get_transaction(id)` auprès de l'API Shwary
6. Anti-rejeu (table `webhook_events`)

---

## Sécurité

### Mesures implémentées

| Mesure | Description |
|--------|-------------|
| **Prix côté serveur** | Le montant est toujours recalculé depuis `catalog.py` via `produit_id`. Impossible de payer 1 CDF en modifiant l'URL ou le formulaire. |
| **Secrets isolés** | Clés Shwary et `SECRET_KEY` dans `.env` (jamais commitées). |
| **Appels API serveur** | `merchant_key` jamais exposée au navigateur. |
| **CSRF** | Token de session sur `/pay`, expiration 30 min. |
| **Rate limiting** | 10 req/min sur `/pay`, 30/min sur callback (mémoire process). |
| **Honeypot** | Champ piège invisible anti-bots sur le formulaire. |
| **Cooldown commandes** | 1 commande pending / numéro / produit toutes les 5 min. |
| **Validation entrées** | Téléphone `+243` + 9 chiffres, `produit_id` strict, texte nettoyé. |
| **Callback sécurisé** | Token URL + vérif marchand + montant + confirmation API Shwary. |
| **Anti-rejeu webhooks** | Événements `tx_id:status` enregistrés une seule fois. |
| **En-têtes HTTP** | CSP, X-Frame-Options, nosniff, etc. |
| **Cookies session** | HttpOnly, SameSite=Lax, Secure en prod. |
| **Limite taille requête** | 16 Ko max (`MAX_CONTENT_LENGTH`). |
| **Contrôle démarrage prod** | Refus de lancer si config faible (`FLASK_DEBUG=false`). |
| **Réponses allégées** | `/pay` ne renvoie que `status` et `id` (pas tout le payload Shwary). |

### Limites connues

| Limite | Impact | Mitigation actuelle |
|--------|--------|---------------------|
| Pas de HMAC webhook | Callback falsifiable si token fuit | Token long + vérif API Shwary |
| Rate limit en mémoire | Reset au redémarrage | Acceptable pour petit trafic |
| Données perso en clair (SQLite) | Risque si base compromise | Chiffrement / RGPD à prévoir en prod |
| Pas d'authentification admin | Pas de back-office | À ajouter si gestion commandes nécessaire |
| Callback localhost | Shwary ne peut pas notifier en local | ngrok ou domaine public en prod |

### Niveau de sécurité

- **Développement / tests** : ✅ adapté
- **Petite boutique réelle** : ✅ acceptable avec checklist prod ci-dessous
- **Gros volume** : ⚠️ prévoir Redis pour rate limit, WSGI, monitoring

---

## Installation et lancement

### Prérequis

- Python 3.10+
- Compte marchand [Shwary](https://shwary.com)

### Étapes

```bash
# 1. Cloner le dépôt
git clone <votre-lien-github>
cd site-pour-vente-de-fleur

# 2. Environnement virtuel (recommandé)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

# 3. Dépendances
pip install -r requirements.txt

# 4. Configuration
copy .env.example .env        # Windows
# cp .env.example .env        # Linux / macOS
# Éditer .env avec vos identifiants Shwary

# 5. Lancer
python app.py
```

Ouvrir **http://127.0.0.1:5000**

---

## Configuration (`.env`)

Copier `.env.example` vers `.env` et renseigner :

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Clé Flask (min. 32 caractères aléatoires en prod) |
| `FLASK_DEBUG` | `true` en dev, **`false` en production** |
| `SHWARY_MERCHANT_ID` | UUID marchand (dashboard Shwary) |
| `SHWARY_MERCHANT_KEY` | Clé secrète marchand |
| `SHWARY_SANDBOX` | `true` = tests sans débit réel, `false` = production |
| `SHWARY_CALLBACK_URL` | URL publique HTTPS du webhook (voir ci-dessous) |
| `CALLBACK_PATH_TOKEN` | Token secret dans l'URL callback |
| `USD_TO_CDF_RATE` | Taux de conversion $ → CDF (produits en dollars) |
| `SESSION_COOKIE_SECURE` | `true` si HTTPS actif |
| `CALLBACK_ALLOWED_IPS` | IP Shwary autorisées (optionnel, si publiées) |

**Générer un token callback :**

```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**URL callback à configurer chez Shwary :**

```
https://votre-domaine.com/api/callback/VOTRE_CALLBACK_PATH_TOKEN
```

---

## Ce qui manque encore

### Fonctionnel

- [ ] **Images produits** dans `static/uploads/` (Roserouge.jpg, Tulipebleu.jpg, Petitefleur.jpg)
- [ ] **Barre de recherche** fonctionnelle
- [ ] **Panier** (`cart.html`, `checkout.html` non branchés)
- [ ] **Page de confirmation** après paiement réussi
- [ ] **Notification email/SMS** au client et au vendeur
- [ ] **Back-office** pour voir et gérer les commandes

### Technique / production

- [ ] **Hébergement** avec HTTPS (VPS, Railway, Render, etc.)
- [ ] **Serveur WSGI** (Gunicorn, Waitress) au lieu de `app.run()`
- [ ] **Reverse proxy** (nginx) avec rate limit et SSL
- [ ] **URL callback publique** (Shwary ne peut pas appeler `localhost`)
- [ ] **Base de données** PostgreSQL si trafic important (remplacer SQLite)
- [ ] **Sauvegarde** régulière de `data/orders.db`
- [ ] **Monitoring** et alertes (paiements échoués, callbacks rejetés)
- [ ] **Conformité RGPD** (politique de confidentialité, consentement, durée de rétention)

### Sécurité (optionnel mais recommandé)

- [ ] Rotation des clés Shwary si `.env` a été exposé
- [ ] Liste blanche IP Shwary sur callback (si Shwary publie leurs IP)
- [ ] Chiffrement des données sensibles en base
- [ ] Tests automatisés (paiement, webhook, CSRF)

---

## Checklist production

Avant d'encaisser de **vrais paiements** :

### Configuration

- [ ] `FLASK_DEBUG=false`
- [ ] `SHWARY_SANDBOX=false`
- [ ] `SECRET_KEY` = chaîne aléatoire ≥ 32 caractères
- [ ] `CALLBACK_PATH_TOKEN` = token aléatoire ≥ 24 caractères
- [ ] `SHWARY_CALLBACK_URL` = URL **HTTPS publique** avec le token
- [ ] `SESSION_COOKIE_SECURE=true`
- [ ] `.env` **jamais** commité sur Git

### Infrastructure

- [ ] Domaine + certificat SSL (Let's Encrypt)
- [ ] Serveur WSGI derrière nginx
- [ ] URL callback identique dans `.env` **et** dashboard Shwary
- [ ] Test complet : commande → paiement → callback → statut `paid` en base

### Tests recommandés

1. Commander un produit en sandbox (`SHWARY_SANDBOX=true`)
2. Vérifier le statut `pending` puis validation USSD
3. Simuler ou recevoir un callback et vérifier `data/orders.db`
4. Tenter de modifier le montant dans les outils dev → doit être ignoré
5. Passer en production uniquement après validation complète

### Exemple déploiement (Waitress)

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=8000 app:app
```

Configurer nginx en HTTPS devant le port 8000.

---

## Parcours utilisateur

```
Accueil (/)
  └── Commander un produit
        └── Paiement (/paiement?produit_id=...)
              └── Formulaire : nom, adresse, téléphone
                    └── Payer → POST /pay
                          └── Shwary envoie USSD au téléphone
                                └── Client valide sur mobile
                                      └── Shwary notifie /api/callback/<token>
                                            └── Commande → status "paid"
```

---

## Références

- [Shwary](https://shwary.com) — plateforme de paiement
- [shwary-python sur PyPI](https://pypi.org/project/shwary-python/)
- `README_SHWARY.md` — documentation complète du SDK Shwary

---

<div align="center">
  <i>Projet initialisé par <b>Mr deo unh</b> — évolution Flask + Shwary</i>
</div>
