---
description: >-
  L'évaluation des risques de cybersécurité exigée par le CRA (article 13) : ce qu'elle doit contenir, une démarche en quatre questions, un comparatif des méthodes (STRIDE, EMB3D, LINDDUN, EBIOS RM, IEC 62443-4-1, ISO/IEC 27005, NIST SP 800-30, EN 40000-1-2) et un modèle à copier.
---

# Évaluer les risques de cybersécurité d'un produit

> **Ressource** · [Série « CRA & Dev »](../index.md) · Lecture : environ 7 min

## Ce que demande le CRA

L'évaluation des risques est le point de départ du [Cyber Resilience Act][cra] : c'est
elle qui dit quelles exigences de l'Annexe I s'appliquent au produit, et comment.
L'article 13 en fixe le contenu minimal :

- une analyse des risques « fondée sur l'utilisation prévue et l'utilisation
  raisonnablement prévisible, ainsi que sur les conditions d'utilisation » :
  environnement opérationnel, actifs à protéger, durée prévue d'utilisation
  (paragraphe 3) ;
- pour chaque exigence de l'Annexe I, partie I, point 2 (a à m) : si elle s'applique,
  et comment elle est mise en œuvre (paragraphe 3) ; une exigence écartée demande
  une « justification claire » (paragraphe 4) ;
- comment sont appliqués le point 1 de la partie I et la gestion des vulnérabilités
  de la partie II (paragraphe 3) ;
- un document tenu à jour pendant la période d'assistance (paragraphe 3), versé à la
  documentation technique (paragraphe 4), et pris en compte de la conception à la
  maintenance (paragraphe 2).

Le règlement n'impose aucune méthode.

## Le piège classique

Un document rempli une fois, pour l'audit, à partir d'un modèle générique : il décrit
« un produit connecté », pas le vôtre, et il est périmé à la version suivante.
L'évaluation utile est courte, propre au produit, et vit dans le dépôt à côté du
code.

## La démarche en quatre questions

Le [Threat Modeling Manifesto][tmm] résume la démarche en quatre questions. Elles
couvrent ce que demande l'article 13.

1. **Sur quoi travaillons-nous ?** L'usage prévu et l'usage prévisible, y compris
   détourné ; l'environnement (atelier, domicile, extérieur) ; les actifs à protéger
   (firmware, clés, données, fonction essentielle) ; la durée de vie. Un schéma des
   flux de données, avec les frontières de confiance, en une page.
2. **Qu'est-ce qui peut mal tourner ?** Pour chaque interface et chaque flux du
   schéma, les menaces. Une grille évite les oublis : [STRIDE][stride] (usurpation,
   altération, répudiation, divulgation, déni de service, élévation de privilèges) ;
   pour un appareil embarqué, le catalogue [EMB3D][emb3d] du MITRE.
3. **Que faisons-nous ?** Coter chaque risque en vraisemblance et en impact, sur
   trois niveaux suffisent. Puis décider : une mesure, rattachée au point de
   l'Annexe I qu'elle couvre, ou l'acceptation du risque, justifiée.
4. **Avons-nous bien travaillé ?** Une relecture par quelqu'un qui n'a pas écrit
   l'analyse. Et une mise à jour à chaque version, et à chaque vulnérabilité qui
   change la donne (article 13, paragraphe 7).

## Choisir une méthode

| Méthode | Ce que c'est | Quand la choisir | Accès |
| --- | --- | --- | --- |
| [STRIDE][stride] (Microsoft) | Grille de six catégories de menaces, appliquée au schéma des flux | Point de départ de toute équipe de développement | Libre |
| [EMB3D][emb3d] (MITRE) | Base de menaces et de mesures propres aux appareils embarqués | Firmware et matériel, en complément de STRIDE | Libre |
| [LINDDUN][linddun] | Menaces sur la vie privée | Produit qui traite des données personnelles | Libre |
| [EBIOS Risk Manager][ebios] (ANSSI) | Méthode complète en cinq ateliers, des sources de risque aux scénarios opérationnels | Produit critique, dossier à argumenter devant une direction ou des clients | Libre, FR et EN |
| [NIST SP 800-30][nist] | Guide générique : vocabulaire, échelles, déroulé | Structurer les cotations et le vocabulaire | Libre |
| [IEC 62443-4-1][iec] | Cycle de développement sécurisé ; l'exigence SR-2 demande un modèle de menaces par produit | Produit industriel, client qui exige IEC 62443 | Payant |
| [ISO/IEC 27005][iso] | Gestion des risques de la sécurité de l'information | Risques de l'organisation (SMSI ISO 27001) plutôt que du produit | Payant |
| [EN 40000-1-2][en40000] | Norme harmonisée horizontale du CRA : principes, gestion des risques produit, activités du cycle de vie | Viser la présomption de conformité, une fois la norme publiée | En approbation |

**Pour s'orienter :**

- **Premier exercice, petite équipe** : les quatre questions et STRIDE, plus EMB3D
  pour un appareil embarqué. Quelques heures, et le résultat couvre l'article 13.
- **Données personnelles** : ajoutez LINDDUN.
- **Secteur industriel** : IEC 62443-4-1, que vos clients connaissent déjà.
- **Produit critique, ou besoin d'un dossier argumenté** : EBIOS RM.
- **Présomption de conformité** : un produit conforme à une norme harmonisée dont la
  référence est publiée au Journal officiel est présumé conforme aux exigences
  qu'elle couvre (article 27). EN 40000-1-2 est en approbation ; le CEN-CENELEC
  prévoit sa disponibilité pour le 25 novembre 2026.

## Un modèle à copier

À garder en Markdown dans le dépôt, relu dans les pull requests :

```markdown
# Évaluation des risques : <produit> <version>

## 1. Contexte
- Usage prévu :
- Usage raisonnablement prévisible :
- Environnement d'utilisation :
- Actifs à protéger :
- Durée d'utilisation prévue, période d'assistance :
- Interfaces et flux (schéma) :

## 2. Risques
| # | Menace : qui, par où | Vraisemblance | Impact | Décision | Mesure ou justification |
| --- | --- | --- | --- | --- | --- |

## 3. Annexe I, partie I, point 2
| Point | Applicable ? | Mise en œuvre, ou justification si non applicable |
| --- | --- | --- |
| a) pas de vulnérabilité exploitable connue | | |
| … | | |
| m) effacement des données et réglages | | |

## 4. Annexe I, partie I, point 1, et partie II
- Niveau de cybersécurité visé et pourquoi :
- Gestion des vulnérabilités (SBOM, contact, mises à jour) :

## 5. Historique
| Date | Version | Changement |
| --- | --- | --- |
```

Exemple de lignes pour un capteur LoRaWAN (voir l'[épisode 6](../CRA-Dev-06-FUOTA-LoRaWAN.md)) :

| # | Menace : qui, par où | V. | I. | Décision | Mesure ou justification |
| --- | --- | --- | --- | --- | --- |
| 1 | Firmware malveillant poussé par la mise à jour radio | moyenne | élevé | réduire | Image signée, vérifiée par MCUboot (point 2 c et f) |
| 2 | Vulnérabilité connue dans une dépendance | élevée | élevé | réduire | SBOM et surveillance continue ([épisodes 1](../CRA-Dev-01-SBOM-VEX.md) et [5](../CRA-Dev-05-SBOM-DTRACK.md)) |
| 3 | Brouillage radio | faible | moyen | accepter | Hors de portée de l'appareil ; perte de mesures tolérée par la fonction |

## À retenir

L'évaluation des risques n'est pas un document de plus : c'est celui qui justifie tous
les autres. Quatre questions, une grille de menaces, un tableau des exigences de
l'Annexe I, le tout tenu à jour dans le dépôt : c'est ce que demande l'article 13.
La méthode se choisit selon le produit et ses clients.

[cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=fr
[tmm]: https://www.threatmodelingmanifesto.org/
[stride]: https://learn.microsoft.com/fr-fr/azure/security/develop/threat-modeling-tool-threats
[emb3d]: https://emb3d.mitre.org/
[linddun]: https://linddun.org/
[ebios]: https://cyber.gouv.fr/publications/la-methode-ebios-risk-manager-le-guide
[nist]: https://csrc.nist.gov/pubs/sp/800/30/r1/final
[iec]: https://webstore.iec.ch/en/publication/33615
[iso]: https://www.iso.org/fr/standard/80585.html
[en40000]: https://standards.cencenelec.eu/ords/f?cs=1D72BA048927BF4E6076BA309587EA01A&p=CEN%3A110%3A%3A%3A%3A%3AFSP_PROJECT%2CFSP_ORG_ID%3A81335%2C2307986
