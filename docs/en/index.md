# "CRA & Dev" series

Short articles, readable in a few minutes, with one development technique each time,
to help developers secure their software and move toward the requirements of the
Cyber Resilience Act (Regulation (EU) 2024/2847).


Who it's for: developers, with no cryptography background required. Each episode
starts from a concrete need, gives an applicable technique with code (Rust, Python,
.NET), and ends with the threat model, meaning what the technique protects and what
it does not.

## Episodes

| # | Title | CRA requirement | Annex I ref. | Platform |
| --- | --- | --- | --- | --- |
| 01 | [Never store a secret in plaintext again: Windows DPAPI](CRA-Dev-01-DPAPI.md) | Confidentiality, encryption at rest | Part I, point 2, (e) | Windows |
| 02 | [Trust, but verify: sign your data](CRA-Dev-02-Integrite.md) | Data integrity | Part I, point 2, (f) | Cross-platform |
| 03 | [You can't fix what you don't know you're running: SBOM and VEX](CRA-Dev-03-SBOM-VEX.md) | Vulnerability handling, SBOM | Part II, point 1 | CI, cross-platform |
| 04 | [An unsigned .exe is a parcel with no sender: sign your binaries](CRA-Dev-04-Authenticode.md) | Integrity and secure updates | Part I, point 2, (c) and (f) | Windows |

The list will grow with each episode.

The references point to Annex I of [Regulation (EU) 2024/2847][cra]. Its Part I lists
the product cybersecurity requirements (points a to m); its Part II covers
vulnerability handling.

In-depth article, a long and sourced version for going deeper:
[DPAPI in detail](ressources/DPAPI-Article-de-fond.md).

[cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=en
