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
