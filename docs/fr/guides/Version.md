---
description: >-
  Conventions de versioning à appliquer : SemVer, pré-releases (alpha, bêta, release candidate) et choix entre PATCH, MINOR et MAJOR.
---

# Versions

| Exemple | Statut | Usage |
|---|---|---|
| `v0.x.y` | Pré-release | Développement initial, API instable |
| `v1.0.0-alpha.1` | Alpha | Fonctionnalités incomplètes |
| `v1.0.0-beta.1` | Bêta | Fonctionnalités complètes, tests et corrections |
| `v1.0.0-rc.1` | Release candidate | Version stable candidate |
| `v1.0.0` | Release | Première version stable publique |
| `v1.0.1` | Correctif | Correction rétrocompatible |
| `v1.1.0` | Mineure | Nouvelle fonctionnalité rétrocompatible |
| `v2.0.0` | Majeure | Changement incompatible |

| Changement | Version |
|---|---|
| Correction compatible | `PATCH` : `v1.0.1` |
| Fonctionnalité compatible | `MINOR` : `v1.1.0` |
| Code, configuration ou usage à adapter | `MAJOR` : `v2.0.0` |

## Exemple global

| Version | Évolution du bootloader |
|---|---|
| `v0.1.0` | Prototype USB, encore instable |
| `v1.0.0-alpha.1` | Mise à jour USB incomplète |
| `v1.0.0-beta.1` | Toutes les fonctions sont présentes, début des tests |
| `v1.0.0-rc.1` | Version candidate prête pour validation |
| `v1.0.0` | Première version stable publique |
| `v1.0.1` | Correction d'un bug USB, usage inchangé |
| `v1.1.0` | Ajout facultatif de la vérification de signature |
| `v2.0.0` | Nouveau protocole incompatible avec `v1.x.x` |
