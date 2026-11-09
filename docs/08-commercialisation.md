# Proposer Ruche RH à des entreprises

## Proposition de valeur
- Pointage sans badge ni pointeuse dédiée : une tablette ou un PC avec caméra suffit.
- Adapté au Bénin : jours fériés légaux, paie CNSS/ITS/VPS, bulletins PDF, FCFA, interface en français.
- Un seul outil : employés, présences, congés, paie, recrutement, évaluations, documents.
- Multi-entreprises : un même serveur peut héberger plusieurs clients (offre SaaS ou cabinet RH/comptable).

## Modes de vente possibles
1. **Hébergé par vous (SaaS)** : abonnement par entreprise ou par nombre d'employés ; vous gérez serveur,
   sauvegardes, mises à jour. (La facturation automatique n'est pas incluse.)
2. **Installé chez le client** : licence + installation + maintenance (Docker, voir `02-deploiement.md`).

## Matériel côté client
Tablette Android/iPad ou PC avec webcam correcte, navigateur récent (Chrome/Edge/Safari), connexion
internet, éclairage frontal à l'entrée.

## Avant chaque vente — à régler honnêtement avec le client
- **Données biométriques** : consentement, information des employés, démarches éventuelles auprès de
  l'autorité de protection des données (voir `05-pointage-facial.md`).
- **Paie** : paramètres validés par son comptable ; périmètre non couvert listé dans `06-paie-benin.md`.
- **Limites du pointage facial** (pas de détection du vivant).
- **Sauvegardes** et hébergement : où sont les données, qui les sauvegarde.

## Démonstration en 10 minutes
1. `seed_demo` puis connexion `rh@demo.bj`.
2. Enrôler un visage depuis une fiche employé (webcam du portable).
3. Se connecter avec `borne@demo.bj` dans un autre onglet/navigateur : pointer.
4. Montrer Présences, rapport mensuel, une demande de congé et sa validation.
5. Calculer une période de paie et ouvrir un bulletin PDF.
