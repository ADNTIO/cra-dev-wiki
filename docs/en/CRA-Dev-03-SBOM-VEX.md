# You can't fix what you don't know you're running: SBOM and VEX

> **CRA & Dev #3** · ["CRA & Dev" series](index.md) · Reading time: about 7 min · CI, cross-platform ·
> Tools: cdxgen, CycloneDX, Dependency-Track

## What the CRA requires

This is probably the most structuring obligation of the Cyber Resilience Act. Its
vulnerability handling requirements (Annex I, Part II, point 1) mandate identifying
and documenting the components in a product, in particular by drawing up a **SBOM**
(*Software Bill of Materials*) in a commonly used, machine-readable format, covering
at least the top-level dependencies.

In practice, you must know at any moment what your software contains: which library,
which version, transitive dependencies included. Without that list, you cannot answer
the question that matters the day a flaw drops: am I affected by this CVE?

Think of a vehicle recall. When an airbag turns out to be defective, the supplier
built it, but it is the automaker who fitted it into its vehicles that must recall
the fleet and replace the part, provided it knows which models carry the faulty
batch. You are that automaker: your dependencies are parts supplied by others, and
when a flaw hits one of them, it is on you to know which products embed it and to
ship the update. The SBOM is your fleet registry, the update is the replacement
part, and keeping it current lets you trigger the recall in hours rather than weeks.

> This series presents technical practices that contribute to CRA compliance. On
> their own, they are not enough to demonstrate a product's full compliance.

## The classic trap

Two mistakes come up often.

The first: generating a SBOM once, by hand, to tick the box, then forgetting it. A
frozen SBOM is wrong at the first `npm install` or dependency change. A useful SBOM
is produced **on every build**, automatically.

The second: plugging a scanner into the SBOM and drowning in hundreds of CVEs. Most
of them don't affect you (the vulnerable function is never called, the code path is
dead, a condition isn't met). Without triage, the alert becomes noise, and noise ends
up ignored. That is where VEX comes in.

## Technique 1: produce a SBOM, continuously

The most widespread format is **CycloneDX** (JSON or XML). Each ecosystem has its
generator, and [`cdxgen`][cdxgen] covers most languages with a single tool.

```bash
# Multi-language, auto-detects the ecosystem
npx @cyclonedx/cdxgen@11.7.0 -o bom.json

# Or per ecosystem:
cyclonedx-py environment      # Python
cargo cyclonedx               # Rust
dotnet CycloneDX ./MyApp.sln  # .NET
```

Always pin the tool version, never `@latest` in a pipeline: that is what makes the
SBOM reproducible and stops an upstream update from changing the pipeline's behaviour
without review. Then let Renovate or Dependabot propose the upgrades. What remains is
wiring the generation into CI so it stays alive. Example with GitHub Actions,
publishing the SBOM to a [Dependency-Track][dtrack] server that tracks
vulnerabilities over time:

```yaml
# .github/workflows/sbom.yml
name: SBOM
on: [push]
jobs:
  sbom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate the CycloneDX SBOM
        run: npx @cyclonedx/cdxgen@11.7.0 -o bom.json
      - name: Publish to Dependency-Track
        run: |
          curl -sf -X POST "$DTRACK_URL/api/v1/bom" \
            -H "X-Api-Key: $DTRACK_API_KEY" \
            -F "project=$DTRACK_PROJECT" \
            -F "bom=@bom.json"
        env:
          DTRACK_URL: ${{ secrets.DTRACK_URL }}
          DTRACK_API_KEY: ${{ secrets.DTRACK_API_KEY }}
          DTRACK_PROJECT: ${{ vars.DTRACK_PROJECT_UUID }}
```

On every push, the component list is up to date and checked against vulnerability
databases.

## Technique 2: cut the noise with VEX

VEX (*Vulnerability Exploitability eXchange*) is a document that accompanies the SBOM
and states, for a given CVE, whether your product is actually affected. It isn't
named as such in the CRA, but it directly serves the obligations around handling and
sharing vulnerability information.

[CycloneDX carries VEX][cyclonedx-vex] in the `analysis` field of a vulnerability.
Marking a CVE `not_affected` requires justifying why:

```json
{
  "vulnerabilities": [
    {
      "id": "CVE-2024-12345",
      "analysis": {
        "state": "not_affected",
        "justification": "code_not_reachable",
        "detail": "The library is imported but the vulnerable function is never called."
      },
      "affects": [ { "ref": "pkg:npm/example@1.2.3" } ]
    }
  ]
}
```

CycloneDX states are: `resolved`, `exploitable`, `in_triage`, `false_positive`,
`not_affected`. The justifications allowed for `not_affected` are standardised
(`code_not_present`, `code_not_reachable`, `requires_configuration`,
`requires_dependency`, `requires_environment`, and the `protected_by_*` variants).

There is also the standalone [OpenVEX][openvex] format (statuses `not_affected`,
`affected`, `fixed`, `under_investigation`), generated with `vexctl`, useful if you
want a VEX document independent from the SBOM.

## Three things to know

1. A SBOM is alive, not a one-off deliverable. Generate it on every build. The CRA
   asks at least for top-level dependencies, but aiming for transitive ones gives you
   real visibility.
2. VEX saves you time, and commits you. Declaring a CVE `not_affected` is a dated,
   justified security statement. It must be accurate and revisable: a
   `code_not_reachable` that holds today can become false after a refactor.
3. SBOM and VEX fix nothing. They tell you what to fix and in what order.
   Remediation (updating, patching, dropping a dependency) is still on you, and the
   CRA requires doing it without undue delay.

## Takeaway

A SBOM answers a simple but vital question: what does my software contain? Generated
continuously, it turns a CRA obligation into a steering tool. VEX makes it usable by
separating the vulnerabilities that matter from the noise. Together, they move
vulnerability handling from paperwork to practice.

---

*Previous episode: [Trust, but verify, sign your data](CRA-Dev-02-Integrite.md).*

[cdxgen]: https://github.com/CycloneDX/cdxgen
[dtrack]: https://dependencytrack.org/
[cyclonedx-vex]: https://cyclonedx.org/use-cases/vulnerability-exploitability/
[openvex]: https://github.com/openvex/spec
