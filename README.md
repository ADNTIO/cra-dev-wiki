# CRA & Dev

*[Version française](README.fr.md)*

The "CRA & Dev" series: short articles, one development technique per episode, to help
developers secure their software and move toward the requirements of the European
**Cyber Resilience Act** (Regulation (EU) 2024/2847).

This is not another legal explainer of the CRA. Each episode translates a requirement
of Annex I into a concrete engineering practice, with runnable code (Rust, Python,
.NET and more), no cryptography background required, and a threat model at the end
(what the technique protects, and what it does not).

## Published site

The wiki is published with **MkDocs Material** and deployed to GitHub Pages:

- https://adntio.github.io/cra-dev-wiki/

The site is bilingual (French default, English under `/en/`), with full-text search
and a language switcher.

## Episodes

| # | Title | CRA requirement | Annex I | Platform |
| --- | --- | --- | --- | --- |
| 01 | [You can't fix what you don't know you're running: SBOM and VEX](https://adntio.github.io/cra-dev-wiki/en/CRA-Dev-01-SBOM-VEX/) | Vulnerability handling | Part II, 1 | CI |
| 02 | [An unsigned .exe is a parcel with no sender: sign your binaries](https://adntio.github.io/cra-dev-wiki/en/CRA-Dev-02-Authenticode/) | Integrity and secure updates | Part I, 2 (c) and (f) | Windows |
| 03 | [Never store a secret in plaintext again: Windows DPAPI](https://adntio.github.io/cra-dev-wiki/en/CRA-Dev-03-DPAPI/) | Confidentiality, encryption at rest | Part I, 2 (e) | Windows |
| 04 | [Trust, but verify: sign your data](https://adntio.github.io/cra-dev-wiki/en/CRA-Dev-04-Integrite/) | Data integrity | Part I, 2 (f) | Cross-platform |
| 05 | [Generating an SBOM is not enough: monitor it with Dependency-Track](CRA-Dev-05-SBOM-DTRACK.md) | Vulnerability handling, continuous monitoring | Part II, point 1 | CI, cross-platform |


## Repository layout

```
mkdocs.yml               MkDocs Material + i18n configuration
requirements-docs.txt    Pinned build dependencies
docs/
  fr/                    French content (default language)
    index.md
    CRA-Dev-0X-*.md
    guides/              conventions to apply
    ressources/          in-depth articles
  en/                    English content (same paths as fr/)
.github/workflows/docs.yml   Build and deploy to GitHub Pages
```

The French and English versions of a page share the **same path** under `docs/fr/`
and `docs/en/`; this is what lets the i18n plugin pair them and offer the language
switch.

## Build locally

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv venv
uv pip install -r requirements-docs.txt
uv run mkdocs serve      # live preview on http://127.0.0.1:8000
uv run mkdocs build --strict
```

## Deployment

Pushing to `main` triggers `.github/workflows/docs.yml`, which builds the site and
deploys it to GitHub Pages. It requires **Settings > Pages > Source: GitHub Actions**
to be enabled once on the repository.

## Contributing

Spotted an error, a dead link, or want to add a translation? See
[CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Open
an [issue](../../issues) or a [Pull Request](../../pulls).

## License

Copyright © 2026 ADNT Sàrl. Content licensed under
[CC BY-SA 4.0](LICENSE), a free copyleft license recognised as free by the Free
Software Foundation.
