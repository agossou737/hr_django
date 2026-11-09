# Module de paie (Bénin)

> **Important** — Les taux ont été recoupés auprès de plusieurs sources publiques début novembre 2026,
> mais ils évoluent (lois de finances, décrets). **Chaque entreprise doit faire valider ses paramètres par
> son expert-comptable** avant la première paie réelle. Tous les paramètres sont modifiables dans
> **Paie → Paramètres de paie**, sans toucher au code.

## Paramètres par défaut
| Élément | Valeur par défaut |
|---|---|
| CNSS salarié — vieillesse | 3,6 % |
| CNSS employeur — vieillesse | 6,4 % |
| CNSS employeur — prestations familiales | 9 % |
| CNSS employeur — risques professionnels | 1 % (de 1 à 4 % selon l'activité, **taux notifié par la CNSS**) |
| Plafond CNSS | aucun (champ prévu si le client en a un) |
| VPS (versement patronal sur salaires) | 4 % de la base |
| ITS — barème mensuel progressif | 0 % jusqu'à 60 000 ; 10 % de 60 000 à 150 000 ; 15 % de 150 000 à 250 000 ; 19 % de 250 000 à 500 000 ; 30 % au-delà |
| Arrondis | base ITS au millier inférieur, impôt à la dizaine (désactivable) |
| SMIG | 52 000 FCFA (indicatif) |

Points à confirmer avec le comptable : base de l'ITS (par défaut = brut imposable, **sans** déduction de la
CNSS salarié — case à cocher pour changer), existence d'un plafond CNSS, taux accident du travail.

## Calcul d'un bulletin
```
Brut soumis      = salaire de base − retenue d'absences non payées + primes soumises
Brut             = brut soumis + indemnités non soumises
CNSS salarié     = taux × min(brut soumis, plafond)
ITS              = barème appliqué à la base ITS
Net à payer      = brut − CNSS salarié − ITS − retenues (avances…)
Charges employeur= CNSS employeur + VPS     ;  Coût employeur = brut + charges
```
Exemple de référence (testé) : brut 300 000 → CNSS 10 800, ITS 33 500, **net 255 700** ; CNSS employeur
49 200, VPS 12 000.

- **Salaire de base** : celui du contrat applicable sur le mois (Employés → Contrats).
- **Absences non payées** : jours ouvrés des congés **approuvés** dont le type est « non rémunéré »,
  retenus au prorata `salaire × jours / jours ouvrés du mois`.
- **Éléments variables** : sur chaque bulletin en brouillon, ajouter primes/indemnités (soumises ou non à
  CNSS+ITS) ou retenues (avances, acomptes). Le bulletin est recalculé aussitôt.

## Circuit
1. **Paie → Périodes → Nouvelle période** (un mois).
2. **Calculer les bulletins** (employés avec contrat ; ceux sans contrat sont signalés).
3. Ajuster les éléments variables, **recalculer** si les paramètres changent.
4. **Valider** : les valeurs sont figées, les bulletins deviennent visibles par les employés (Mes
   bulletins). **Rouvrir** permet de corriger tant que nécessaire.
5. Exports : journal de paie (Excel, CSV), état CNSS (CSV), bulletins PDF individuels.

## Ce qui n'est pas géré (à ne pas promettre)
- Proratisation d'un salaire pour une **embauche ou un départ en cours de mois** (saisir un ajustement
  négatif manuel).
- Heures supplémentaires, 13ᵉ mois, indemnités de préavis/licenciement (régimes fiscaux spécifiques),
  avantages en nature, prêts avec échéancier.
- Majoration ORTB (redevance audiovisuelle), assurance maladie obligatoire (décret 2025-672, dont les
  modalités d'application sont à suivre), télédéclaration CNSS/DGI.
- Charges de famille : aucune déduction n'est appliquée à l'ITS dans les sources consultées.
