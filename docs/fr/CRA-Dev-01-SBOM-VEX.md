# Vous ne pouvez pas corriger ce que vous ignorez : SBOM et VEX

> **CRA & Dev #1** · [Série « CRA & Dev »](index.md) · Lecture : environ 7 min · CI, multiplateforme ·
> Outils : cdxgen, CycloneDX, Dependency-Track

## Ce que demande le CRA

C'est sans doute l'obligation la plus structurante du Cyber Resilience Act. Sa
gestion des vulnérabilités (Annexe I, partie II, point 1) impose d'identifier et de
documenter les composants d'un produit, notamment en établissant un **SBOM**
(*Software Bill of Materials*) dans un format courant et lisible par machine,
couvrant au minimum les dépendances de premier niveau.

En pratique, vous devez savoir à tout instant ce que contient votre logiciel :
quelle bibliothèque, quelle version, dépendances transitives comprises. Sans cette
liste, impossible de répondre à la question qui compte le jour d'une faille : suis-je
concerné par cette CVE ?

C'est la logique du rappel automobile. Quand un airbag se révèle défectueux,
l'équipementier l'a fabriqué, mais c'est le constructeur qui l'a monté dans ses
véhicules qui doit rappeler sa flotte et remplacer la pièce, à condition de savoir
quels modèles embarquent le lot en cause. Vous êtes ce constructeur : vos
dépendances sont des pièces fournies par d'autres, et quand une faille touche l'une
d'elles, c'est à vous de savoir quels produits l'embarquent et de livrer la mise à
jour. Le SBOM est votre registre de flotte, la mise à jour est le remplacement de la
pièce, et le tenir à jour permet de déclencher le rappel en heures plutôt qu'en
semaines.

> Cette série présente des pratiques techniques qui contribuent à la conformité au
> CRA. Leur mise en œuvre ne suffit pas, à elle seule, à démontrer la conformité
> complète d'un produit.

## Le piège classique

Deux erreurs reviennent souvent.

La première : générer un SBOM une fois, à la main, pour cocher la case, puis
l'oublier. Un SBOM figé devient faux au premier `npm install` ou changement de
dépendance. Un SBOM utile est produit **à chaque build**, automatiquement.

La seconde : brancher un scanner sur le SBOM et crouler sous des centaines de CVE.
La plupart ne vous concernent pas (fonction vulnérable jamais appelée, chemin de
code mort, condition non remplie). Sans tri, l'alerte devient du bruit, et le bruit
finit ignoré. C'est là qu'intervient VEX.

## La technique 1 : produire un SBOM, en continu

Le format le plus répandu est **CycloneDX** (JSON ou XML). Chaque écosystème a son
générateur, et [`cdxgen`][cdxgen] couvre la plupart des langages d'un seul outil.

```bash
# Multi-langage, détecte automatiquement l'écosystème
npx @cyclonedx/cdxgen@11.7.0 -o bom.json

# Ou par écosystème :
cyclonedx-py environment      # Python
cargo cyclonedx               # Rust
dotnet CycloneDX ./MyApp.sln  # .NET
```

Épinglez toujours la version de l'outil, jamais `@latest` dans un pipeline : c'est
ce qui rend le SBOM reproductible et empêche une mise à jour amont de changer le
comportement du pipeline sans revue. Laissez ensuite Renovate ou Dependabot proposer
les montées de version. Il reste à intégrer la génération à la CI pour qu'elle reste
vivante. Exemple avec GitHub Actions, en publiant le SBOM vers un serveur
[Dependency-Track][dtrack] qui suit les vulnérabilités dans le temps :

```yaml
# .github/workflows/sbom.yml
name: SBOM
on: [push]
jobs:
  sbom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Générer le SBOM CycloneDX
        run: npx @cyclonedx/cdxgen@11.7.0 -o bom.json
      - name: Publier vers Dependency-Track
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

À chaque push, la liste des composants est à jour et confrontée aux bases de
vulnérabilités.

## La technique 2 : trier le bruit avec VEX

VEX (*Vulnerability Exploitability eXchange*) est un document qui accompagne le
SBOM et dit, pour une CVE donnée, si votre produit est réellement affecté. Il n'est
pas nommé tel quel dans le CRA, mais il sert directement les obligations de gestion
et de partage d'informations sur les vulnérabilités.

[CycloneDX porte VEX][cyclonedx-vex] dans le champ `analysis` d'une vulnérabilité.
Marquer une CVE `not_affected` impose de justifier pourquoi :

```json
{
  "vulnerabilities": [
    {
      "id": "CVE-2024-12345",
      "analysis": {
        "state": "not_affected",
        "justification": "code_not_reachable",
        "detail": "La bibliothèque est importée mais la fonction vulnérable n'est jamais appelée."
      },
      "affects": [ { "ref": "pkg:npm/example@1.2.3" } ]
    }
  ]
}
```

Les états CycloneDX sont : `resolved`, `exploitable`, `in_triage`, `false_positive`,
`not_affected`. Les justifications possibles pour `not_affected` sont normalisées
(`code_not_present`, `code_not_reachable`, `requires_configuration`,
`requires_dependency`, `requires_environment`, et les variantes `protected_by_*`).

Il existe aussi le format autonome [OpenVEX][openvex] (statuts `not_affected`,
`affected`, `fixed`, `under_investigation`), qu'on génère avec `vexctl`, utile si
vous voulez un document VEX indépendant du SBOM.

## Trois choses à savoir

1. Un SBOM est vivant, pas un livrable ponctuel. Générez-le à chaque build. Le CRA
   demande au minimum les dépendances de premier niveau, mais viser les transitives
   donne une vraie visibilité.
2. VEX vous fait gagner du temps, et vous engage. Déclarer une CVE `not_affected`
   est une affirmation de sécurité datée et justifiée. Elle doit être exacte et
   révisable : un `code_not_reachable` d'aujourd'hui peut devenir faux après un
   refactor.
3. SBOM et VEX ne corrigent rien. Ils vous disent quoi corriger et dans quel ordre.
   La remédiation (mettre à jour, patcher, retirer une dépendance) reste à faire,
   et le CRA impose de la mener sans délai injustifié.

## À retenir

Le SBOM répond à une question simple mais vitale : que contient mon logiciel ?
Généré en continu, il transforme une obligation du CRA en outil de pilotage. VEX le
rend exploitable en séparant les vulnérabilités qui comptent du bruit. Ensemble, ils
font passer la gestion des vulnérabilités du déclaratif au concret.

---

*Épisode suivant : [Un colis sans expéditeur, signez vos
binaires](CRA-Dev-02-Authenticode.md).*

[cdxgen]: https://github.com/CycloneDX/cdxgen
[dtrack]: https://dependencytrack.org/
[cyclonedx-vex]: https://cyclonedx.org/use-cases/vulnerability-exploitability/
[openvex]: https://github.com/openvex/spec
