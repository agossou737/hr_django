# Ruche RH — gestion RH & pointage par reconnaissance faciale (Django)

Plateforme RH **multi-entreprises**, en français, pensée pour le **Bénin / zone OHADA** : pointage par
reconnaissance faciale depuis le navigateur, congés, paie (CNSS, ITS, VPS), recrutement, évaluations et
documents RH.

## Fonctionnalités

| Module | Contenu |
|---|---|
| **Employés** | Fiches (matricule auto, CNSS, IFU), départements, postes, contrats, export CSV |
| **Pointage facial** | Borne dans le navigateur (face-api.js, hors ligne), enrôlement avec consentement, arrivée/départ, retards, journal des scans, présences du jour, rapport mensuel |
| **Pointage par empreinte** | Biométrie du téléphone/PC (WebAuthn, aucune donnée biométrique stockée) et lecteurs USB via API |
| **Congés et permissions** | Types, demandes, soldes, chevauchements, **remplaçant (intérim) à confirmer et délégation**, permissions de quelques heures, validation manager/RH, calendrier, autorisations PDF |
| **Explications de retard** | Demande automatique dès qu'un retard est détecté, PDF à l'employé, réponse en ligne, PDF de réponse aux RH, décision, relances |
| **Notifications** | Cloche dans l'application + e-mails |
| **Matériel** | Inventaire, affectation, restitution, décharge PDF |
| **Réunions** | Convocations, comptes rendus PDF, actions suivies |
| **Notes de frais, formations, discipline** | Circuits de validation, attestations et notifications PDF |
| **Exports et imports** | Excel / PDF / CSV partout ; import massif des employés avec aperçu |
| **Paie Bénin** | CNSS, ITS (barème progressif), VPS, congés non payés, primes/retenues, périodes validables, **bulletins PDF**, journal Excel/CSV, état CNSS |
| **Recrutement** | Offres, candidatures par étapes, CV privé, embauche en un clic |
| **Évaluations** | Grille de critères, brouillon → transmission → prise en compte par l'employé |
| **Documents RH** | Stockage privé, alertes d'expiration |
| **Paramètres** | Horaires, jours fériés du Bénin générés, utilisateurs et rôles |

Rôles : Administrateur, Responsable RH, Manager, Employé, Borne de pointage. Les données de chaque
entreprise sont strictement cloisonnées.

## Démarrage rapide
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo      # rh@demo.bj / borne@demo.bj — mot de passe demo12345
python manage.py runserver      # http://localhost:8000
```
Nouveau client : `python manage.py create_company --name "Client SARL" --admin-email rh@client.bj`

## Documentation (`docs/`)
1. [Installation](docs/01-installation.md)
2. [Déploiement en production](docs/02-deploiement.md) (Docker, nginx, HTTPS, sauvegardes)
3. [Guide administrateur / mise en service d'un client](docs/03-guide-administrateur.md)
4. [Guide utilisateur](docs/04-guide-utilisateur.md)
5. [Pointage facial : fonctionnement, limites, données personnelles](docs/05-pointage-facial.md)
6. [Paie Bénin : paramètres, calcul, périmètre](docs/06-paie-benin.md)
7. [Architecture technique](docs/07-architecture.md)
8. [Proposer le produit à des entreprises](docs/08-commercialisation.md)
9. [Circuits employé ↔ RH, matériel, réunions, empreinte digitale, frais, formations, discipline](docs/09-circuits-employe-rh.md)

## Points d'attention
- **HTTPS obligatoire** en production (la caméra du navigateur l'exige hors `localhost`).
- **Paie** : faire valider les paramètres par l'expert-comptable du client avant usage réel.
- **Biométrie** : consentement et obligations légales à vérifier avec un juriste ; pas de détection du « vivant ».

## Tests
```bash
python manage.py test     # 124 tests
```

## Licences tierces
Template d'interface Lineone (licence de son éditeur), face-api.js / @vladmandic/face-api (MIT,
`static/vendor/face-api/LICENSE`).
