# Contribuer / Contributing

[Français](#français) · [English](#english)

---

## Français

Merci de vouloir améliorer le wiki « CRA & Dev ». Ce projet vit grâce aux
relectures. Une coquille, une imprécision technique, un lien mort, une meilleure
formulation, une traduction : tout est utile.

### Vous avez repéré une erreur

Deux façons de contribuer, au choix.

1. Ouvrir une issue, la voie la plus simple, sans aucune connaissance de Git. Allez
   dans l'onglet Issues du dépôt GitHub, puis New issue, et décrivez le problème. Si
   possible, précisez :
   - le fichier concerné, par exemple `fr/CRA-Dev-01-DPAPI.md` ;
   - la nature de l'erreur : technique, orthographe, lien, traduction ;
   - la correction proposée, si vous l'avez.

2. Proposer une Pull Request, pour appliquer directement la correction.
   - Forkez le dépôt, créez une branche (`fix/dpapi-typo`, `trad/en-episode-01`).
   - Faites votre modification.
   - Ouvrez une Pull Request en décrivant le changement et en liant l'issue
     éventuelle avec `Fixes #123`.

### Règles de fond, importantes pour ce wiki

- Ne jamais inventer une source. Toute affirmation technique doit renvoyer à une
  source primaire : doc officielle, whitepaper, RFC, texte réglementaire. Les liens
  se gèrent en style référence markdown, avec les définitions regroupées en bas de
  page.
- Le français est la langue source. Une correction de fond doit d'abord être portée
  en français, puis répercutée en anglais, et inversement pour signaler un décalage.
- Rester dans l'esprit de la série : court, orienté développeur, sans prérequis
  crypto, avec le modèle de menace à la fin.
- Code d'exemple testable. Privilégiez des extraits qui compilent ou s'exécutent, et
  des API vérifiées.

### Style

- Un sujet égale une contribution. Évitez les PR fourre-tout.
- Messages de commit courts et explicites.
- Respectez la structure par langue (`fr/`, `en/`) et le nommage des pages wiki
  (`CRA-Dev-0X-Sujet.md`).

En participant, vous acceptez le [Code de conduite](CODE_OF_CONDUCT.md).

---

## English

Thanks for helping improve the "CRA & Dev" wiki. This project thrives on reviews. A
typo, a technical inaccuracy, a dead link, a better wording, a translation:
everything helps.

### Spotted an error

Two ways to contribute.

1. Open an issue, the easiest way, with no Git knowledge required. Go to the
   repository's Issues tab, then New issue, and describe the problem. If possible,
   include:
   - the file involved, for example `en/CRA-Dev-01-DPAPI.md`;
   - the type of error: technical, spelling, link, translation;
   - your suggested fix, if you have one.

2. Open a Pull Request, to apply the fix directly.
   - Fork the repo, create a branch (`fix/dpapi-typo`, `trad/en-episode-01`).
   - Make your change.
   - Open a Pull Request describing the change and linking any issue with
     `Fixes #123`.

### Substance rules, important for this wiki

- Never invent a source. Every technical claim must point to a primary source:
  official docs, whitepaper, RFC, regulatory text. Links use markdown reference
  style, with definitions grouped at the bottom of the page.
- French is the source language. A substantive fix should land in French first, then
  be mirrored in English, and vice versa when flagging a mismatch.
- Stay in the spirit of the series: short, developer-focused, no crypto prerequisite,
  with the threat model at the end.
- Runnable example code. Prefer snippets that compile or run, and verified APIs.

### Style

- One topic per contribution. Avoid catch-all PRs.
- Short, explicit commit messages.
- Respect the per-language structure (`fr/`, `en/`) and the wiki page naming
  convention (`CRA-Dev-0X-Topic.md`).

By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
