"""Build the example risk assessments to PDF: Markdown + a generated diagram."""
from pathlib import Path

import markdown
from weasyprint import HTML

HERE = Path(__file__).parent
DOCS = HERE.parent.parent / "docs"

# (language, source, output PDF, diagram labels)
EXAMPLES = [
    ("fr", "capteur-ensoleillement", "evaluation-risques-capteur-ensoleillement"),
    ("fr", "sonde-niveau-eau", "evaluation-risques-sonde-niveau-eau"),
    ("en", "sunlight-sensor", "evaluation-risques-capteur-ensoleillement"),
    ("en", "water-level-sensor", "evaluation-risques-sonde-niveau-eau"),
]

LABELS = {
    "fr": {"field": "Terrain (accès physique)", "net": "Réseau LoRaWAN (opérateur)",
           "op": "Exploitant", "maker": "Fabricant", "gw": "Passerelle", "ns": "Serveur réseau",
           "as": "Serveur d'application", "ui": ("Supervision", ["tableau de bord", "alertes"]),
           "sign": "Clé de signature", "image": "image signée, mise à jour (FUOTA)",
           "radio": "LoRaWAN : chiffré, authentifié"},
    "en": {"field": "Field (physical access)", "net": "LoRaWAN network (operator)",
           "op": "Operator", "maker": "Manufacturer", "gw": "Gateway", "ns": "Network server",
           "as": "Application server", "ui": ("Monitoring", ["dashboard", "alerts"]),
           "sign": "Signing key", "image": "signed image, update (FUOTA)",
           "radio": "LoRaWAN: encrypted, authenticated"},
}


def box(x, y, w, h, title, lines=(), fill="#ffffff", stroke="#94a3b8"):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>',
           f'<text x="{x + w / 2}" y="{y + 20}" text-anchor="middle" font-size="12" font-weight="700" fill="#0f172a">{title}</text>']
    for i, line in enumerate(lines):
        out.append(f'<text x="{x + w / 2}" y="{y + 40 + i * 16}" text-anchor="middle" font-size="11" fill="#334155">{line}</text>')
    return "\n".join(out)


def zone(x, y, w, h, label, color):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="6 4"/>'
            f'<text x="{x + 10}" y="{y + 16}" font-size="11" font-weight="700" fill="{color}">{label}</text>')


def arrow(x1, y1, x2, y2, label="", dashed=False, both=False):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    start = ' marker-start="url(#a)"' if both else ""
    out = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#0e7490" stroke-width="1.6"{dash}{start} marker-end="url(#a)"/>'
    if label:
        out += f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 7}" text-anchor="middle" font-size="10.5" fill="#0e7490">{label}</text>'
    return out


def marker(n, x, y, color="#b91c1c"):
    return (f'<circle cx="{x}" cy="{y}" r="10" fill="{color}"/>'
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">{n}</text>')


def diagram(lang, device_title, device_lines, risks, color="#b91c1c"):
    t = LABELS[lang]
    parts = [
        '<rect width="920" height="270" fill="#ffffff"/>',
        zone(10, 10, 205, 250, t["field"], "#b45309"),
        zone(225, 10, 305, 135, t["net"], "#475569"),
        zone(545, 10, 365, 250, t["op"], "#0e7490"),
        zone(225, 160, 305, 100, t["maker"], "#6d28d9"),
        box(25, 40, 175, 200, device_title, device_lines, fill="#fff7ed", stroke="#b45309"),
        box(240, 50, 115, 60, t["gw"]),
        box(385, 50, 125, 60, t["ns"]),
        box(555, 50, 170, 60, t["as"]),
        box(740, 50, 160, 76, t["ui"][0], t["ui"][1]),
        box(240, 185, 130, 45, t["sign"], fill="#f5f3ff", stroke="#6d28d9"),
        arrow(200, 80, 240, 80, dashed=True, both=True),
        arrow(355, 80, 385, 80, both=True),
        arrow(510, 80, 555, 80, both=True),
        arrow(725, 80, 740, 80),
        arrow(370, 207, 640, 110),
        f'<text x="440" y="252" text-anchor="middle" font-size="10" fill="#6d28d9">{t["image"]}</text>',
        f'<text x="375" y="133" text-anchor="middle" font-size="10" fill="#0e7490">{t["radio"]}</text>',
    ]
    parts += [marker(n, x, y, color) for n, x, y in risks]
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 270" width="100%">'
            '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M0 0 L10 5 L0 10 z" fill="#0e7490"/></marker></defs>'
            '<g font-family="DejaVu Sans, Helvetica, Arial, sans-serif">' + "\n".join(parts) + "</g></svg>")


CSS = """
@page { size: A4; margin: 16mm 15mm; @bottom-right { content: counter(page) " / " counter(pages); font-size: 8pt; color: #64748b; } }
body { font-family: "DejaVu Sans", Helvetica, Arial, sans-serif; font-size: 9.5pt; line-height: 1.45; color: #0f172a; }
h1 { font-size: 17pt; margin: 0 0 4pt; }
h2 { font-size: 12pt; margin: 14pt 0 5pt; border-bottom: 1px solid #cbd5e1; padding-bottom: 2pt; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; font-size: 8.5pt; }
th, td { border: 1px solid #cbd5e1; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #f1f5f9; }
tr { page-break-inside: avoid; }
blockquote { margin: 6pt 0; padding: 5pt 9pt; background: #fef3c7; border-left: 3px solid #b45309; }
blockquote p { margin: 0; }
svg { margin: 4pt 0 2pt; }
"""


PAGE_INTRO = {
    "fr": "Version PDF : [{name}.pdf]({name}.pdf). Source : `examples/07-risk-assessment/{lang}/{source}.md`.",
    "en": "PDF version: [{name}.pdf]({name}.pdf). Source: `examples/07-risk-assessment/{lang}/{source}.md`.",
}

# The four trust boundaries of the LoRaWAN sensor, for the episode page.
BOUNDARIES = [("A", 220, 80), ("B", 533, 80), ("C", 545, 144), ("D", 12, 150)]


def build(lang, source, output):
    text = (HERE / lang / f"{source}.md").read_text()
    meta, body = text.split("\n---\n", 1)
    conf = dict(line.split(": ", 1) for line in meta.strip().splitlines())
    risks = [tuple(int(v) for v in r.split(",")) for r in conf["markers"].split()]
    svg = diagram(lang, conf["device"], conf["lines"].split(" | "), risks)
    out = DOCS / lang / "ressources" / "exemples"
    out.mkdir(parents=True, exist_ok=True)

    html = markdown.markdown(body.replace("{{schema}}", svg), extensions=["tables", "md_in_html"])
    page = f'<html lang="{lang}"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{html}</body></html>'
    HTML(string=page).write_pdf(out / f"{output}.pdf")

    # The same assessment as a page of the site, with its diagram as an SVG file.
    (out / f"{output}.svg").write_text(svg)
    title = next(line for line in body.splitlines() if line.startswith("# "))[2:]
    intro = PAGE_INTRO[lang].format(name=output, lang=lang, source=source)
    md = body.replace("{{schema}}", f"![{title}]({output}.svg)")
    md = md.replace("## 1.", f"{intro}\n\n## 1.", 1)
    (out / f"{output}.md").write_text(f"---\ndescription: >-\n  {title}\n---\n{md}")
    print(out.relative_to(DOCS.parent) / output)

    if source in ("capteur-ensoleillement", "sunlight-sensor"):
        images = DOCS / lang / "images"
        images.mkdir(exist_ok=True)
        boundaries = diagram(lang, conf["device"], conf["lines"].split(" | "), BOUNDARIES, color="#b45309")
        (images / "frontieres-de-confiance.svg").write_text(boundaries)


if __name__ == "__main__":
    for example in EXAMPLES:
        build(*example)
