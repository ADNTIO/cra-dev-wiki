---
description: >-
  Série CRA & Dev : le Cyber Resilience Act (règlement (UE) 2024/2847) traduit en gestes d'ingénierie — SBOM et VEX, signature de binaires, secrets chiffrés, intégrité des données, mises à jour de firmware par LoRaWAN, journaux signés — avec du code exécutable en Rust, Python, .NET et C.
---

# Série « CRA & Dev »

Des articles courts, lisibles en quelques minutes, avec une technique de
développement à chaque fois, pour aider les développeurs à sécuriser leur logiciel
et à se rapprocher des exigences du Cyber Resilience Act (Règlement (UE) 2024/2847).


Pour qui : des développeurs, sans prérequis en cryptographie. Chaque épisode part
d'un besoin concret, donne une technique applicable avec du code (Rust, Python,
.NET, C), et se termine par le modèle de menace, c'est-à-dire ce que la technique
protège et ce qu'elle ne protège pas.

## Épisodes

| # | Titre | Exigence CRA | Réf. Annexe I | Plateforme |
| --- | --- | --- | --- | --- |
| 01 | [Vous ne pouvez pas corriger ce que vous ignorez : SBOM et VEX](CRA-Dev-01-SBOM-VEX.md) | Gestion des vulnérabilités, SBOM | Partie II, point 1 | CI, multiplateforme |
| 02 | [Un .exe non signé, c'est un colis sans expéditeur : signez vos binaires](CRA-Dev-02-Authenticode.md) | Intégrité et mise à jour sécurisée | Partie I, point 2, c) et f) | Windows |
| 03 | [Ne stockez plus jamais un secret en clair : la DPAPI de Windows](CRA-Dev-03-DPAPI.md) | Confidentialité, chiffrement au repos | Partie I, point 2, e) | Windows |
| 04 | [Faites confiance, mais vérifiez : signer vos données](CRA-Dev-04-Integrite.md) | Intégrité des données | Partie I, point 2, f) | Multiplateforme |
| 05 | [Générer un SBOM ne suffit pas : surveillez-le avec Dependency-Track](CRA-Dev-05-SBOM-DTRACK.md) | Gestion des vulnérabilités, surveillance continue | Partie II, point 1 | CI, multiplateforme |
| 06 | [Mille fragments, une seule signature : mettre à jour un firmware par LoRaWAN](CRA-Dev-06-FUOTA-LoRaWAN.md) | Mises à jour de sécurité, distribution sécurisée | Partie I, point 2, c) ; partie II, point 7 | Embarqué, LoRaWAN |
| 07 | [Un journal qui ne peut pas mentir : chaîner et signer ses logs](CRA-Dev-07-Signed-Logs.md) | Journalisation et surveillance de l'activité interne | Partie I, point 2, l) | Multiplateforme |

La liste s'enrichira au fil des épisodes.

Les références renvoient à l'Annexe I du [Règlement (UE) 2024/2847][cra]. Sa partie I
liste les exigences de cybersécurité des produits (points a à m) ; sa partie II
couvre la gestion des vulnérabilités.

Article de fond, version longue et sourcée pour approfondir :
[la DPAPI en détail](ressources/DPAPI-Article-de-fond.md).

[cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=fr
