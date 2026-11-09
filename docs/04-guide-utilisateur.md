# Guide utilisateur

## Employé
- **Mon espace** (tableau de bord) : pointage du jour, soldes de congés, dernières demandes.
- **Congés → Mes congés → Nouvelle demande** : type, dates, motif. Le nombre de jours ouvrés est calculé
  automatiquement (week-ends et jours fériés exclus). Refus automatique si le solde est insuffisant ou si
  les dates chevauchent une autre demande. Une demande en attente ou à venir peut être annulée.
- **Paie → Mes bulletins** : bulletins PDF des périodes **validées** par les RH.
- **Évaluations → Mes évaluations** : évaluations transmises ; bouton « J'ai pris connaissance » avec
  commentaire facultatif.
- **Documents → Mes documents** : téléchargement de ses propres pièces.

## Manager
Tout ce qui précède, plus :
- **Congés → Demandes à traiter** : approuver/refuser (commentaire facultatif) les demandes de son équipe.
  On ne peut jamais traiter sa propre demande.
- **Évaluations → Évaluations de l'équipe** : créer une évaluation (6 critères notés de 1 à 5, points forts,
  axes d'amélioration, objectifs), l'enregistrer en brouillon, puis **la transmettre** à l'employé (elle
  n'est alors plus modifiable).

## Responsable RH / Administrateur
- **Employés** : fiches, départements, postes, contrats ; export CSV (respecte les filtres).
- **Pointage** : présences du jour (présent / retard / absent / congé), correction manuelle, rapport
  mensuel (export CSV), journal de toutes les tentatives de scan.
- **Congés** : toutes les demandes (export CSV), saisie d'un congé au nom d'un employé (approuvé
  directement), calendrier, types de congés.
- **Paie** : voir `06-paie-benin.md`.
- **Recrutement** : offres → candidatures (étapes : nouvelle, présélection, entretien, offre) → bouton
  **Créer la fiche employé** (matricule automatique, candidature marquée « Embauché »).
- **Documents** : pièces des employés (PDF, Word, JPG, PNG ; 5 Mo max) avec date d'expiration ; page
  « Documents à renouveler » (expirés ou à moins de 60 jours) et alerte sur le tableau de bord.
- **Paramètres** : entreprise et horaires, jours fériés, utilisateurs.

## Borne de pointage
1. Se connecter avec le compte « borne » sur la tablette/PC d'accueil (HTTPS), autoriser la caméra.
2. L'employé se place devant la caméra : le nom, l'action (arrivée/départ) et l'heure s'affichent.
3. Règle : **premier passage de la journée = arrivée**, passages suivants = mise à jour de l'heure de
   départ. Deux passages à moins de 2 minutes ne comptent qu'une fois.
4. Retard = arrivée après l'heure de début + tolérance définies dans les paramètres de l'entreprise.

### Enrôler un visage
Fiche employé → **Enrôler le visage** : cocher la case de consentement, lancer la capture (5 échantillons
automatiques, personne face caméra, bien éclairée, sans lunettes de soleil ni masque). Il est possible de
réenrôler à tout moment ou de **supprimer** les données faciales.
