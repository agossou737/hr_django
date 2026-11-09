# Architecture technique

## Pile
Django 5.2 · Python 3.11+ · SQLite (dev) / PostgreSQL (prod) · Tailwind + Alpine.js (template Lineone,
CSS précompilé) · face-api.js (navigateur) · reportlab (PDF) · openpyxl (Excel) · WhiteNoise + gunicorn.

## Modules (applications Django)
| App | Contenu |
|---|---|
| `companies` | Entreprise (tenant), horaires, jours fériés, paramètres, commande `create_company`, exports CSV |
| `accounts` | Utilisateur (e-mail), rôles, connexion, gestion des utilisateurs, tableau de bord |
| `employees` | Départements, postes, employés (matricule auto), contrats |
| `attendance` | Empreintes faciales, pointages, journal des scans, rapports, borne et enrôlement |
| `leaves` | Types de congés, demandes, soldes, validation, calendrier |
| `payroll` | Paramètres, périodes, bulletins, calculateur pur (`calculator.py`), PDF, exports |
| `recruitment` | Offres, candidatures, embauche |
| `evaluations` | Évaluations par critères, workflow brouillon → transmise → prise en compte |
| `documents` | Documents RH, expirations, stockage privé |
| `config` | Réglages, URL, navigation par rôle (`context.py`), stockage privé (`files.py`) |

## Multi-entreprise et sécurité
- Tout modèle métier hérite de `CompanyOwnedModel` (clé `company`).
- Les vues utilisent `CompanyQuerysetMixin` (filtre par entreprise), `CompanyFormMixin` (listes déroulantes
  filtrées, entreprise imposée côté serveur) et des mixins de rôle (`HRRequiredMixin`,
  `KioskRequiredMixin`…). Un identifiant d'une autre entreprise renvoie **404**.
- CSRF actif partout, y compris sur l'API de scan (cookie CSRF envoyé par la page de la borne).
- Fichiers confidentiels dans `private/`, sans URL publique (`PrivateStorage.url()` lève une erreur).
- Production : cookies sécurisés, HSTS, redirection HTTPS, refus de démarrer sans `SECRET_KEY`.

## Intégrations entre modules
`attendance` ↔ `leaves` (statut « en congé »), `leaves`/`payroll` (congés non payés → retenue),
`recruitment` → `employees` (embauche), `documents`/`leaves` → tableau de bord (alertes).

## Tests
124 tests (`python manage.py test`) : calcul de paie (cas de référence), règles de pointage, soldes de
congés, droits par rôle, **isolation entre entreprises** pour chaque module, validation des fichiers.

## Pistes d'évolution
Détection du vivant, API REST/application mobile, notifications e-mail/SMS/WhatsApp, heures
supplémentaires et prorata de paie, paramétrage de critères d'évaluation par entreprise,
télédéclarations CNSS/DGI, facturation/abonnement des clients (SaaS), double authentification.
