# Ruche RH — Logiciel de gestion RH (Django)

Plateforme RH multi-entreprises pensée pour le marché béninois / zone OHADA, avec pointage par reconnaissance faciale (phase 2).

## Phase 1 (livrée)

- Multi-entreprise (une entreprise = un « tenant », données strictement isolées)
- Utilisateurs identifiés par e-mail, 4 rôles : Administrateur, Responsable RH, Manager, Employé
- Départements, postes, fiches employés (matricule automatique `EMP0001`, CNSS, IFU…)
- Contrats (CDI, CDD, stage, prestation, apprentissage)
- Tableau de bord (effectifs, dernières embauches, contrats arrivant à échéance)
- Interface web en français (Tailwind), administration Django

## Interface

Basée sur le template **Lineone** (Tailwind + Alpine.js) dans `static/`. Le nom du produit s'affiche partout via
`APP_NAME` (variable `.env` ou `config/settings.py`). Le CSS du template étant un build purgé, les classes
manquantes sont ajoutées dans `static/css/custom.css`.

> Lineone est un template commercial : une licence adaptée est nécessaire pour une revente à des clients.

## Feuille de route

| Phase | Contenu |
|-------|---------|
| 2 | Pointage facial par la caméra du navigateur, présences, journal des tentatives |
| 3 | Congés et absences (workflow de validation) |
| 4 | Paie Bénin (CNSS, IRPP/ITS, bulletins PDF) |
| 5 | Recrutement, évaluations, documents RH, exports |

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # puis ajuster
python manage.py migrate
python manage.py createsuperuser # compte plateforme (sans entreprise)
python manage.py seed_demo       # optionnel : rh@demo.bj / demo12345
python manage.py runserver
```

Pour PostgreSQL, renseigner `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` dans `.env`
(sinon SQLite est utilisé).

## Mise en route d'un client

1. Dans `/admin/`, créer l'**Entreprise**.
2. Créer un **Utilisateur** rattaché à cette entreprise avec le rôle *Responsable RH*.
3. Ce compte se connecte sur `/compte/connexion/` et gère départements, postes, employés et contrats.

## Tests

```bash
python manage.py test
```
