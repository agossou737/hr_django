# Déploiement en production

Deux méthodes équivalentes. Dans les deux cas : **HTTPS obligatoire** (sans lui, la caméra du
navigateur est bloquée et la borne de pointage ne fonctionne pas).

## Variables d'environnement essentielles (`.env`)
| Variable | Rôle |
|---|---|
| `SECRET_KEY` | **Obligatoire** et secrète. Le démarrage échoue avec `DEBUG=False` si elle est absente/par défaut. |
| `DEBUG` | `False` en production. Active cookies sécurisés, HSTS, redirection HTTPS. |
| `ALLOWED_HOSTS` | Noms de domaine, ex. `rh.mon-domaine.bj` |
| `CSRF_TRUSTED_ORIGINS` | ex. `https://rh.mon-domaine.bj` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL (SQLite si `DB_NAME` vide) |

Générer une clé : `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`

## Méthode A — Docker
```bash
cp .env.example .env     # renseigner SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, DB_PASSWORD
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py create_company --name "Client SARL" --admin-email rh@client.bj
```
L'application écoute sur `127.0.0.1:8000` : placez devant un reverse proxy HTTPS
(`deploy/nginx.conf.example`, ou Caddy/Traefik).

## Méthode B — Serveur Linux (systemd + nginx)
```bash
sudo apt install python3-venv nginx postgresql
git clone … /srv/ruche-rh && cd /srv/ruche-rh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
```
Puis installer `deploy/ruche-rh.service.example` (systemd) et `deploy/nginx.conf.example`
(nginx + certificat Let's Encrypt via `certbot --nginx`).

## Fichiers : ce qui est public, ce qui ne l'est pas
- `media/` : logos d'entreprises et photos d'employés — servi par nginx (`/media/`).
- `private/` : **CV et documents RH**. Aucune URL publique n'existe ; ils sont servis uniquement par
  l'application après contrôle des droits. **Ne jamais exposer ce dossier dans nginx.**

## Sauvegardes
`deploy/backup.sh.example` sauvegarde la base et les fichiers (`media/` + `private/`) ; à planifier en
cron quotidien et à copier hors du serveur. Testez régulièrement une restauration.

## Mises à jour
```bash
git pull && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate && .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart ruche-rh
```

## Contrôle avant mise en ligne
```bash
DEBUG=False python manage.py check --deploy
```
Seul l'avertissement `SECURE_HSTS_PRELOAD` est attendu (volontairement non activé).
