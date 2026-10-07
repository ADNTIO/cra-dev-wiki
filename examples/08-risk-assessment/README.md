# Example: two risk assessments, built to PDF

Companion files for episode 8 of the "CRA & Dev" series,
[Assessing the cybersecurity risks of a product](../../docs/en/CRA-Dev-08-Evaluation-Risques.md).

Two fictional LoRaWAN products, assessed with the template of the page, in French
and English:

| Product | Stakes | Sources |
| --- | --- | --- |
| LS-1 sunlight sensor | low: a wrong reading only affects operations | `fr/capteur-ensoleillement.md`, `en/sunlight-sensor.md` |
| NV-2 water level probe for public reservoirs | high: a firefighting reserve may depend on it | `fr/sonde-niveau-eau.md`, `en/water-level-sensor.md` |

## Build

This project uses [uv](https://docs.astral.sh/uv/). WeasyPrint needs Pango on the
host (`apt install libpango-1.0-0 libpangoft2-1.0-0` on Debian or Ubuntu).

```bash
uv run python build.py
```

`build.py` turns each Markdown file into HTML, draws its diagram (the numbered
markers point to the risks of the table), and writes the PDF to
`docs/<lang>/ressources/exemples/`, together with the same assessment as a page of
the site and its diagram as SVG. It also draws the trust boundary diagram of the
episode, `docs/<lang>/images/frontieres-de-confiance.svg`.
