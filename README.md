# ADNT, wiki « CRA & Dev »

Wiki de la série « CRA & Dev » : des articles courts, une technique de développement
à chaque fois, pour aider les développeurs à sécuriser leur logiciel et à se
rapprocher des exigences du Cyber Resilience Act (Règlement (UE) 2024/2847).

## Langues / Languages

| Langue | Accueil |
| --- | --- |
| Français | [Accueil](fr/Home.md) |
| English | [Home](en/Home.md) |

Le français est la langue source, l'anglais en est la traduction. Les articles de
fond longs (versions détaillées et sourcées) sont pour l'instant disponibles en
français, avec une traduction anglaise progressive.

## Organisation du dépôt

Ce dépôt est structuré comme un wiki GitHub, avec un dossier par langue :

```
.
├── README.md              (vous êtes ici, sélecteur de langue)
├── fr/                    (wiki français, langue source)
│   ├── Home.md            (page d'accueil)
│   ├── _Sidebar.md        (navigation latérale)
│   ├── _Footer.md         (pied de page)
│   ├── CRA-Dev-01-DPAPI.md
│   └── ressources/        (articles de fond, versions longues)
└── en/                    (English wiki, translation)
    ├── Home.md
    ├── _Sidebar.md
    ├── _Footer.md
    ├── CRA-Dev-01-DPAPI.md
    └── resources/
```

Les fichiers `Home.md`, `_Sidebar.md` et `_Footer.md` suivent les conventions du
wiki GitHub. Si le contenu est publié dans un vrai wiki (dépôt `.wiki.git`), GitHub
utilise le `_Sidebar.md` ou `_Footer.md` le plus proche dans l'arborescence, ce qui
permet une navigation propre par langue.

## À qui s'adresse cette série

Aux développeurs, sans prérequis en cryptographie. Chaque épisode part d'un besoin
concret, donne une technique directement applicable avec du code (Rust, Python,
.NET), et introduit au passage les notions de crypto utiles. Voir la page d'accueil
de chaque langue pour le détail.

## Contribuer

Une erreur, une imprécision, un lien mort, une amélioration ou une traduction ? Les
relectures sont les bienvenues. Deux façons de contribuer :

- Signaler : ouvrez une [issue](../../issues) sur GitHub, aucune connaissance de Git
  requise.
- Corriger : proposez une [Pull Request](../../pulls).

Merci de lire d'abord le [guide de contribution](CONTRIBUTING.md) et le
[code de conduite](CODE_OF_CONDUCT.md).

## Licence

Copyright © 2026 ADNT Sàrl.

Contenu publié sous licence [Creative Commons Attribution - Partage dans les Mêmes
Conditions 4.0 International (CC BY-SA 4.0)](LICENSE), une licence libre et copyleft
reconnue comme licence libre par la Free Software Foundation. Vous pouvez partager et
adapter le contenu, y compris à des fins commerciales, à condition de créditer ADNT
Sàrl et de diffuser vos versions sous la même licence.
