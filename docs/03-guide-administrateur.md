# Guide de l'éditeur / administrateur de la plateforme

## Principe multi-entreprises
Une installation héberge plusieurs entreprises clientes. Chaque donnée (employés, pointages, congés,
paie…) est rattachée à une entreprise et **jamais visible depuis une autre** (cloisonnement vérifié par
les tests automatiques).

## Mettre en service un nouveau client (≈ 2 minutes)
```bash
python manage.py create_company --name "Raison sociale du client" \
    --admin-email rh@client.bj --first-name Prénom --last-name Nom
```
(le mot de passe est demandé en saisie masquée). La commande crée : l'entreprise, son administrateur,
les types de congés usuels, les jours fériés légaux de l'année et les paramètres de paie par défaut.

Le client se connecte ensuite sur `/compte/connexion/` et complète **Paramètres → Entreprise et horaires**
(raison sociale, IFU, RCCM, n° employeur CNSS, horaires, jours travaillés).

## Rôles
| Rôle | Peut faire |
|---|---|
| **Administrateur** | Tout dans son entreprise, y compris créer d'autres administrateurs |
| **Responsable RH** | Tout dans son entreprise sauf créer/modifier un administrateur |
| **Manager** | Valider les congés et évaluer **son équipe** (employés dont il est le supérieur ou dont il dirige le département) ; voir ses propres bulletins/documents |
| **Employé** | Ses congés, bulletins validés, évaluations transmises, documents |
| **Borne de pointage** | Uniquement la page de pointage (compte à mettre sur la tablette/PC d'accueil) |

Un utilisateur est relié à une **fiche employé** (Paramètres → Utilisateurs) pour accéder à ses
données personnelles. Sans ce lien, il n'a pas d'espace personnel.

## Check-list de démarrage chez un client
1. Entreprise renseignée, horaires et jours travaillés corrects, **jours fériés générés** (et fêtes
   musulmanes ajoutées à la main — voir plus bas).
2. Départements, postes, employés (fiche + **contrat avec salaire de base**).
3. **Paramètres de paie** relus avec l'expert-comptable du client (taux CNSS, taux accident du travail
   notifié par la CNSS, barème ITS).
4. Types de congés ajustés à la convention collective.
5. Compte « borne » créé ; borne testée en HTTPS ; **enrôlement du visage de chaque employé** avec son
   consentement.
6. Comptes utilisateurs créés et reliés aux fiches employés.

## Fêtes musulmanes
Aïd el-Fitr, Aïd el-Kébir et Maouloud dépendent de l'observation de la lune et sont fixées par décret :
les ajouter chaque année dans **Paramètres → Jours fériés**.

## Mots de passe
Il n'y a pas de « mot de passe oublié » par e-mail (pas de serveur de messagerie imposé) : le
Responsable RH ou l'Administrateur réinitialise le mot de passe depuis **Paramètres → Utilisateurs**.
