---
description: >-
  The cybersecurity risk assessment required by the CRA (Article 13): what it must contain, a four-question approach, a comparison of methods (STRIDE, EMB3D, LINDDUN, EBIOS RM, IEC 62443-4-1, ISO/IEC 27005, NIST SP 800-30, EN 40000-1-2) and a template to copy.
---

# Assessing the cybersecurity risks of a product

> **Resource** · ["CRA & Dev" series](../index.md) · Reading time: about 7 min

## What the CRA requires

The risk assessment is the starting point of the [Cyber Resilience Act][cra]: it is
what says which Annex I requirements apply to the product, and how. Article 13 sets
its minimum content:

- an analysis of the risks "based on the intended purpose and reasonably foreseeable
  use, as well as the conditions of use": operational environment, assets to be
  protected, expected time in use (paragraph 3);
- for each requirement of Annex I, Part I, point 2 (a to m): whether it applies, and
  how it is implemented (paragraph 3); a requirement left out needs "a clear
  justification" (paragraph 4);
- how point 1 of Part I and the vulnerability handling of Part II are applied
  (paragraph 3);
- a document kept up to date during the support period (paragraph 3), included in
  the technical documentation (paragraph 4), and taken into account from design to
  maintenance (paragraph 2).

The regulation imposes no method.

## The classic trap

A document filled in once, for the audit, from a generic template: it describes "a
connected product", not yours, and it is out of date by the next release. The useful
assessment is short, specific to the product, and lives in the repository next to
the code.

## The four-question approach

The [Threat Modeling Manifesto][tmm] sums up the approach in four questions. They
cover what Article 13 asks for.

1. **What are we working on?** The intended use and the foreseeable use, misuse
   included; the environment (workshop, home, outdoors); the assets to protect
   (firmware, keys, data, essential function); the lifetime. A data flow diagram,
   with the trust boundaries, on one page.
2. **What can go wrong?** For each interface and each flow of the diagram, the
   threats. A checklist avoids gaps: [STRIDE][stride] (spoofing, tampering,
   repudiation, information disclosure, denial of service, elevation of privilege);
   for an embedded device, MITRE's [EMB3D][emb3d] catalogue.
3. **What are we going to do about it?** Rate each risk by likelihood and impact;
   three levels are enough. Then decide: a measure, tied to the Annex I point it
   covers, or accepting the risk, with a justification.
4. **Did we do a good enough job?** A review by someone who did not write the
   analysis. And an update with each release, and with each vulnerability that
   changes the picture (Article 13, paragraph 7).

## Choosing a method

| Method | What it is | When to choose it | Access |
| --- | --- | --- | --- |
| [STRIDE][stride] (Microsoft) | Checklist of six threat categories, applied to the data flow diagram | Starting point for any development team | Free |
| [EMB3D][emb3d] (MITRE) | Knowledge base of threats and mitigations specific to embedded devices | Firmware and hardware, on top of STRIDE | Free |
| [LINDDUN][linddun] | Privacy threats | Product that processes personal data | Free |
| [EBIOS Risk Manager][ebios] (ANSSI) | Full method in five workshops, from risk sources to operational scenarios | Critical product, a case to argue before management or customers | Free, FR and EN |
| [NIST SP 800-30][nist] | Generic guide: vocabulary, scales, process | Structuring the ratings and the vocabulary | Free |
| [IEC 62443-4-1][iec] | Secure development lifecycle; requirement SR-2 asks for a threat model per product | Industrial product, customer requiring IEC 62443 | Paid |
| [ISO/IEC 27005][iso] | Information security risk management | Risks of the organisation (ISO 27001 ISMS) rather than of the product | Paid |
| [EN 40000-1-2][en40000] | Horizontal harmonised standard for the CRA: principles, product risk management, lifecycle activities | Aiming for presumption of conformity, once the standard is published | Under approval |

**Finding your way:**

- **First exercise, small team**: the four questions and STRIDE, plus EMB3D for an
  embedded device. A few hours, and the result covers Article 13.
- **Personal data**: add LINDDUN.
- **Industrial sector**: IEC 62443-4-1, which your customers already know.
- **Critical product, or a case to argue**: EBIOS RM.
- **Presumption of conformity**: a product that conforms to a harmonised standard
  whose reference is published in the Official Journal is presumed to conform to the
  requirements it covers (Article 27). EN 40000-1-2 is under approval; CEN-CENELEC
  plans its availability for 25 November 2026.

## A template to copy

Kept in Markdown in the repository, reviewed in pull requests:

```markdown
# Risk assessment: <product> <version>

## 1. Context
- Intended purpose:
- Reasonably foreseeable use:
- Conditions of use, environment:
- Assets to protect:
- Expected time in use, support period:
- Interfaces and flows (diagram):

## 2. Risks
| # | Threat: who, through what | Likelihood | Impact | Decision | Measure or justification |
| --- | --- | --- | --- | --- | --- |

## 3. Annex I, Part I, point 2
| Point | Applicable? | Implementation, or justification if not applicable |
| --- | --- | --- |
| (a) no known exploitable vulnerability | | |
| … | | |
| (m) removal of data and settings | | |

## 4. Annex I, Part I, point 1, and Part II
- Target cybersecurity level and why:
- Vulnerability handling (SBOM, contact, updates):

## 5. History
| Date | Version | Change |
| --- | --- | --- |
```

Example rows for a LoRaWAN sensor (see [episode 6](../CRA-Dev-06-FUOTA-LoRaWAN.md)):

| # | Threat: who, through what | L. | I. | Decision | Measure or justification |
| --- | --- | --- | --- | --- | --- |
| 1 | Malicious firmware pushed through the radio update | medium | high | reduce | Signed image, verified by MCUboot (point 2 (c) and (f)) |
| 2 | Known vulnerability in a dependency | high | high | reduce | SBOM and continuous monitoring ([episodes 1](../CRA-Dev-01-SBOM-VEX.md) and [5](../CRA-Dev-05-SBOM-DTRACK.md)) |
| 3 | Radio jamming | low | medium | accept | Out of the device's reach; loss of readings tolerated by the function |

## Takeaway

The risk assessment is not one more document: it is the one that justifies all the
others. Four questions, a threat checklist, a table of the Annex I requirements, all
kept up to date in the repository: that is what Article 13 asks for. The method is
chosen according to the product and its customers.

[cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=en
[tmm]: https://www.threatmodelingmanifesto.org/
[stride]: https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats
[emb3d]: https://emb3d.mitre.org/
[linddun]: https://linddun.org/
[ebios]: https://messervices.cyber.gouv.fr/guides/en-ebios-risk-manager-method
[nist]: https://csrc.nist.gov/pubs/sp/800/30/r1/final
[iec]: https://webstore.iec.ch/en/publication/33615
[iso]: https://www.iso.org/standard/80585.html
[en40000]: https://standards.cencenelec.eu/ords/f?cs=1D72BA048927BF4E6076BA309587EA01A&p=CEN%3A110%3A%3A%3A%3A%3AFSP_PROJECT%2CFSP_ORG_ID%3A81335%2C2307986
