# Installation (poste de développement ou démonstration)

## Prérequis
- Python 3.11 ou plus récent
- Git
- (Production uniquement) PostgreSQL 14+ — SQLite suffit pour une démonstration

## Étapes
```bash
git clone https://github.com/agossou737/hr_django.git
cd hr_django
python -m venv .venv
source .venv/bin/activate            # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # puis ajuster si besoin
python manage.py migrate
python manage.py seed_demo           # données de démonstration (optionnel)
python manage.py runserver
```
Ouvrir <http://localhost:8000>.

| Compte de démo | Mot de passe | Usage |
|---|---|---|
| `rh@demo.bj` | `demo12345` | Responsable RH (accès complet à l'entreprise) |
| `borne@demo.bj` | `demo12345` | Borne de pointage (tablette/ordinateur d'accueil) |

> **Caméra** : les navigateurs n'autorisent la caméra que sur `localhost` ou en **HTTPS**.
> En développement, `http://localhost:8000` fonctionne ; ailleurs (réseau local, serveur) il faut HTTPS.

## Compte « super-administrateur » de la plateforme
```bash
python manage.py createsuperuser     # accès à /admin/, sans entreprise
```
Il sert à vous (éditeur du logiciel) ; vos clients n'en ont pas besoin.

## Tests
```bash
python manage.py test                # 124 tests
```

## Personnalisation de la marque
Dans `.env` : `APP_NAME` et `APP_TAGLINE`. Le logo se remplace dans `static/images/app-logo.svg`
et `static/images/favicon.png`.
