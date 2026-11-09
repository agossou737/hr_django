# Pointage par reconnaissance faciale — fonctionnement, limites, conformité

## Fonctionnement
1. La page de la borne charge **face-api.js** (modèles inclus dans `static/vendor/face-api/`, aucun
   service externe, fonctionne hors ligne côté navigateur).
2. Le navigateur détecte le visage et calcule une **empreinte numérique de 128 valeurs**.
3. Seule cette empreinte est envoyée au serveur (`POST /pointage/api/scan/`). **Aucune photo ni vidéo
   n'est transmise ni stockée.**
4. Le serveur compare l'empreinte à celles des employés **de la même entreprise** (distance euclidienne,
   seuil `FACE_MATCH_THRESHOLD`, 0,5 par défaut) et enregistre le pointage.
5. Chaque tentative (réussie, inconnue, doublon, employé inactif) est journalisée.

## Réglages
- `FACE_MATCH_THRESHOLD` : plus bas = plus strict (moins de faux positifs, plus de refus). Plage utile
  0,4 – 0,6.
- `ATTENDANCE_MIN_INTERVAL_MINUTES` : anti-doublon.

## Limites connues (à connaître avant de vendre)
- **Pas de détection du « vivant »** : une photo tenue devant la caméra peut tromper le système. À
  atténuer par l'organisation (borne placée sous le regard de l'accueil/gardien) ; une détection du vivant
  est une évolution possible.
- La qualité dépend de l'éclairage et de la caméra. Prévoir un éclairage frontal correct à l'entrée.
- Le calcul s'effectue dans le navigateur : sur une très vieille tablette, la reconnaissance sera lente.
- **HTTPS obligatoire** (exigence des navigateurs pour la caméra), hors `localhost`.
- Comme tout système biométrique, des erreurs sont possibles : la RH peut corriger manuellement tout
  pointage (page Présences).
- Les tests automatiques couvrent la logique serveur (appariement, règles de pointage, isolation entre
  entreprises). Le comportement avec **vos caméras réelles** doit être validé en situation.

## Données personnelles
L'empreinte faciale est une **donnée biométrique**, donc sensible. Points à prévoir avec chaque client :
- **Consentement** : la case de consentement est obligatoire à l'enrôlement et la date est conservée.
- **Information** des employés (finalité : contrôle des horaires), durée de conservation, droit de
  suppression : le bouton « Supprimer les données faciales » l'applique immédiatement.
- Le Bénin dispose d'un cadre légal sur les données personnelles (Code du numérique, autorité de
  protection : APDP) qui peut imposer une **déclaration/autorisation préalable** pour les traitements
  biométriques. **À faire valider par un juriste** pour chaque client — ce document n'est pas un avis
  juridique.
