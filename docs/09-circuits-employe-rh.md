# Circuits employé ↔ RH (étape 7)

## Notifications
Cloche dans l'en-tête (compteur de non lues) + page « Notifications ». Chaque événement important crée une
notification interne et, si SMTP est configuré (`.env.example`), un e-mail. L'envoi d'e-mail n'est jamais bloquant.

## Demandes d'explication
* **Retard** : dès qu'un pointage dépasse la tolérance, une demande est créée automatiquement
  (désactivable dans *Paramètres → Entreprise*, délai de réponse réglable).
* L'employé voit la demande (et son **PDF**) dans *Explications → Mes demandes*, y répond dans l'application.
* Sa réponse génère un **PDF de réponse** destiné aux RH, qui décident : *Justifié* / *Non justifié* (l'employé est notifié).
* **Relances** : `python manage.py send_explanation_reminders` (cron quotidien) — 1 relance par jour, 3 au maximum,
  puis alerte aux RH. Exemple cron : `0 8 * * * cd /app && python manage.py send_explanation_reminders`.
* Les RH peuvent aussi émettre une demande manuelle (absence, autre) ; export Excel/PDF/CSV de la liste.

## Congés avec intérim
* Le demandeur peut désigner un **remplaçant**, qui doit **accepter** (*Congés → Mes remplacements*).
* Tant que le remplaçant n'a pas confirmé, un manager ne peut pas approuver (les RH le peuvent).
* **Délégation** : pendant un congé approuvé d'un manager, son remplaçant ayant accepté peut traiter les
  demandes (congés, permissions) de l'équipe de ce manager, et uniquement pendant la période.
* Un congé approuvé génère une **autorisation de congé PDF**.

## Permissions (absence de quelques heures)
Demande par l'employé (date + créneau + motif), validation par le manager/les RH, notification, **autorisation PDF**,
liste RH exportable.

# Matériel et réunions (étape 8)

## Affectation de matériel
* *Matériel → Inventaire* : fiche par bien (code inventaire unique, catégorie, n° de série, valeur, état), filtres, export Excel/PDF/CSV.
* **Affecter** à un employé (un bien ne peut avoir qu'une affectation ouverte) → l'employé est notifié et retrouve sa
  **décharge PDF** dans *Mon matériel*.
* **Restitution** : date + état au retour ; un bien en mauvais état passe en « maintenance ». Historique complet conservé.
* Un bien déjà affecté ne peut ni être supprimé ni réformé ; un bien avec historique ne se supprime pas (on le réforme).

## Réunions et comptes rendus
* Admin / RH / managers planifient une réunion (date, lieu ou lien visio, ordre du jour, participants) : les participants
  reçoivent une **convocation** (notification + e-mail + PDF).
* Après la réunion, l'organisateur (ou les RH) rédige le **compte rendu** : il est publié, les participants sont notifiés
  et un **PDF de compte rendu** est disponible.
* **Actions / décisions** : chaque action a un responsable et une échéance ; le responsable est notifié et la coche lui-même.
* Visibilité : organisateur, participants et RH uniquement (jamais d'autres entreprises).

# Empreinte digitale (étape 9)

Deux méthodes, qui alimentent le même pointage (source « Empreinte digitale ») et déclenchent les mêmes règles
(retard, demande d'explication automatique, journal des scans).

## 1. Téléphones et PC — WebAuthn
* Aucune donnée biométrique n'est transmise ni stockée : l'empreinte (ou Face ID, Windows Hello…) déverrouille une
  clé cryptographique dans l'appareil ; le serveur ne garde que la **clé publique** et vérifie une **signature**
  (défi à usage unique, domaine vérifié, vérification biométrique obligatoire, compteur anti-clonage).
* **HTTPS obligatoire** (sauf `localhost`). Le domaine est déduit de la requête ; si besoin, fixer `WEBAUTHN_RP_ID`
  et `WEBAUTHN_ORIGIN` dans `.env`.
* Enregistrement : l'employé ouvre *Pointage → Mes appareils biométriques* sur son téléphone/PC et clique sur
  « Enregistrer cet appareil » (les RH peuvent aussi le faire depuis la fiche employé, sur l'appareil concerné).
* Pointage : *Pointage → Pointer par empreinte*.
  * **Mode borne** (compte borne, RH, admin) : n'importe quel employé enregistré sur cet appareil peut pointer.
  * **Mode personnel** : réservé aux entreprises qui cochent « Autoriser le pointage par empreinte depuis le
    téléphone/PC de l'employé » (*Entreprise et horaires*) ; l'employé ne peut utiliser que **son** appareil.
    Désactivé par défaut car il permet de pointer hors des locaux.
* Les RH révoquent un appareil à tout moment (*Pointage → Empreintes et lecteurs*).

## 2. Lecteurs d'empreintes USB / terminaux — API
1. *Empreintes et lecteurs* → créer un lecteur : une **clé secrète** est affichée une seule fois (stockée hachée).
2. Enregistrer les doigts dans le lecteur avec son logiciel, puis déclarer la **correspondance identifiant lecteur → employé**.
3. Un petit agent sur le PC du lecteur envoie chaque passage :

```
POST /biometrie/api/lecteur/
Authorization: Bearer rr_xxxxxxxx
{"user_id": "12", "timestamp": "2026-03-02T07:58:00+01:00"}   # timestamp facultatif (7 jours max)
```
Réponses : `200` pointage enregistré (ou doublon), `404` identifiant inconnu, `401` clé invalide/désactivée.
Un agent d'exemple prêt à l'emploi est fourni : `deploy/lecteur_agent.py` (lecture d'un fichier CSV ou de l'entrée
standard ; adaptable à un terminal ZKTeco via `pyzk`).

## Limites à connaître
* Le lecteur USB doit être raccordé à un PC allumé et connecté (ou un terminal réseau) qui exécute l'agent.
* L'empreinte WebAuthn dépend du matériel de l'appareil (capteur ou reconnaissance faciale du téléphone).

# Modules RH complémentaires (étape 10)

## Notes de frais
Employé : objet, catégorie, date, montant, justificatif (PDF/image, stocké en privé). Validation par le manager
(ou son remplaçant délégué) ou les RH ; jamais par soi-même. Les RH marquent la note « remboursée ». Fiche PDF, export Excel/PDF/CSV.

## Formations
Catalogue (organisme, dates, lieu, coût), inscription groupée d'employés (notification), suivi du statut
(inscrit / suivie / absent) et **attestation de formation PDF** pour les formations suivies. Export des participants.

## Discipline
Réservé aux RH (les managers n'y ont pas accès) : avertissement verbal/écrit, blâme, mise à pied, autre mesure,
rattachable à une demande d'explication. L'employé est notifié, consulte le **PDF de notification** et
**confirme sa prise de connaissance** (horodatée). Export de la liste.

# Accès de connexion des employés

Créer une fiche ou importer des employés **ne crée pas** de compte : l'accès se crée explicitement.
* **Un employé** : fiche employé → « Accès à l'application » → *Créer l'accès* (e-mail + rôle Employé/Manager).
* **Tous d'un coup** : liste des employés → *Créer les accès* (ceux qui ont une adresse e-mail et pas encore de compte).
* **À l'import** : case « Créer aussi les comptes de connexion » avant de confirmer.
* Un **mot de passe temporaire** est affiché une seule fois (imprimable) et envoyé par e-mail ; l'employé doit en choisir un
  nouveau à sa première connexion. Il peut ensuite le changer à tout moment (menu du profil → *Changer mon mot de passe*).
* *Réinitialiser le mot de passe* est disponible sur la fiche pour un compte existant.
* La connexion ignore la casse de l'adresse e-mail (`Jean@X.bj` = `jean@x.bj`).
