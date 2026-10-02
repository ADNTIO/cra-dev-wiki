# CRA & Dev

*[English version](README.md)*

La série « CRA & Dev » : des articles courts, une technique de développement par
épisode, pour aider les développeurs à sécuriser leur logiciel et à se rapprocher des
exigences du **Cyber Resilience Act** européen (Règlement (UE) 2024/2847).

Ce n'est pas une énième vulgarisation juridique du CRA. Chaque épisode traduit une
exigence de l'Annexe I en un geste d'ingénierie concret, avec du code exécutable
(Rust, Python, .NET, etc.), sans prérequis en cryptographie, et se termine par le
modèle de menace (ce que la technique protège, et ce qu'elle ne protège pas).

## Site publié

Le wiki est publié avec **MkDocs Material** et déployé sur GitHub Pages :

- https://adntio.github.io/cra-dev-wiki/

Le site est bilingue (français par défaut, anglais sous `/en/`), avec recherche
plein texte et sélecteur de langue.

## Épisodes

| # | Titre | Exigence CRA | Annexe I | Plateforme |
| --- | --- | --- | --- | --- |
| 01 | [Vous ne pouvez pas corriger ce que vous ignorez : SBOM et VEX](https://adntio.github.io/cra-dev-wiki/CRA-Dev-01-SBOM-VEX/) | Gestion des vulnérabilités | Partie II, 1 | CI |
| 02 | [Un .exe non signé, c'est un colis sans expéditeur : signez vos binaires](https://adntio.github.io/cra-dev-wiki/CRA-Dev-02-Authenticode/) | Intégrité et mise à jour sécurisée | Partie I, 2 c) et f) | Windows |
| 03 | [Ne stockez plus jamais un secret en clair : la DPAPI de Windows](https://adntio.github.io/cra-dev-wiki/CRA-Dev-03-DPAPI/) | Confidentialité, chiffrement au repos | Partie I, 2 e) | Windows |
| 04 | [Faites confiance, mais vérifiez : signer vos données](https://adntio.github.io/cra-dev-wiki/CRA-Dev-04-Integrite/) | Intégrité des données | Partie I, 2 f) | Multiplateforme |
| 05 | [Générer un SBOM ne suffit pas : surveillez-le avec Dependency-Track](CRA-Dev-05-SBOM-DTRACK.md) | Gestion des vulnérabilités, surveillance continue | Partie II, point 1 | CI, multiplateforme |
| 06 | [Mille fragments, une seule signature : mettre à jour un firmware par LoRaWAN](https://adntio.github.io/cra-dev-wiki/CRA-Dev-06-FUOTA-LoRaWAN/) | Mises à jour de sécurité, distribution sécurisée | Partie I, 2 c) ; partie II, 7 | Embarqué, LoRaWAN |

## Organisation du dépôt

```
mkdocs.yml               Configuration MkDocs Material + i18n
requirements-docs.txt    Dépendances de build épinglées
docs/
  fr/                    Contenu français (langue par défaut)
    index.md
    CRA-Dev-0X-*.md
    ressources/          articles de fond
  en/                    Contenu anglais (mêmes chemins que fr/)
examples/
  0X-sujet/              Code d'accompagnement d'un épisode, avec ses tests
.github/workflows/docs.yml   Build et déploiement vers GitHub Pages
```

Les versions française et anglaise d'une page partagent le **même chemin** sous
`docs/fr/` et `docs/en/` : c'est ce qui permet au plugin i18n de les apparier et de
proposer le changement de langue.

## Build local

Ce projet utilise [uv](https://docs.astral.sh/uv/).

```bash
uv venv
uv pip install -r requirements-docs.txt
uv run mkdocs serve      # aperçu en direct sur http://127.0.0.1:8000
uv run mkdocs build --strict
```

## Déploiement

Un push sur `main` déclenche `.github/workflows/docs.yml`, qui build le site et le
déploie sur GitHub Pages. Il faut activer une fois **Settings > Pages > Source :
GitHub Actions** sur le dépôt.

## Contribuer

Une erreur, un lien mort, une traduction à ajouter ? Voir
[CONTRIBUTING.md](CONTRIBUTING.md) et le [code de conduite](CODE_OF_CONDUCT.md). Ouvrez
une [issue](../../issues) ou une [Pull Request](../../pulls).

## Licence

Copyright © 2026 ADNT Sàrl. Contenu sous licence
[CC BY-SA 4.0](LICENSE), une licence libre et copyleft reconnue comme libre par la
Free Software Foundation.
