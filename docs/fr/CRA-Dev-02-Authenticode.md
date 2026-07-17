# Un .exe non signé, c'est un colis sans expéditeur : signez vos binaires

> **CRA & Dev #2** · [Série « CRA & Dev »](index.md) · Lecture : environ 6 min · Windows ·
> Outils : signtool, PowerShell, Azure Trusted Signing

## Ce que demande le CRA

Deux exigences se rejoignent ici. L'intégrité (Annexe I, partie I, point 2, f) veut
qu'on puisse détecter toute modification non autorisée d'un programme. Le mécanisme
de mise à jour sécurisé (point c) veut que les correctifs arrivent chez
l'utilisateur sans pouvoir être falsifiés en chemin.

La signature de code répond aux deux. Un binaire signé, c'est un colis scellé avec
un expéditeur vérifié : le destinataire peut confirmer qu'il vient bien de vous et
qu'on ne l'a pas ouvert en route. Un `.exe` non signé arrive anonyme, et rien ne
distingue votre installeur de sa version piégée.

Signer une donnée est une chose ; ici, on signe l'exécutable lui-même, avec le
mécanisme natif de Windows : **Authenticode**.

> Cette série présente des pratiques techniques qui contribuent à la conformité au
> CRA. Leur mise en œuvre ne suffit pas, à elle seule, à démontrer la conformité
> complète d'un produit.

## Le piège classique

Trois erreurs, toutes fréquentes.

Signer sans horodater. Une signature seule devient invalide le jour où le certificat
expire, et tous vos binaires déjà distribués basculent en « non signé ». L'horodatage
(*timestamp*) fige la preuve que la signature était valide au moment où elle a été
posée. Elle reste alors valable même après expiration du certificat. Ce n'est pas
optionnel.

Utiliser un certificat auto-signé. Il ne remonte à aucune autorité de confiance :
SmartScreen continue d'alerter, et l'utilisateur voit toujours un avertissement. Pour
être reconnu, le certificat doit venir d'une AC de confiance.

Mettre la clé privée dans le dépôt ou la CI. Depuis le 1er juin 2023, les règles du
CA/Browser Forum imposent que la clé privée d'un certificat de signature de code
reste sur du matériel (token ou HSM, y compris cloud). Un `.pfx` encodé en base64
dans un secret de CI n'est plus conforme, et de toute façon dangereux.

## La technique : signer, horodater, vérifier

La signature se fait avec [`signtool`][signtool]. L'horodatage est fourni par
l'option `/tr`.

```powershell
# Signer avec empreinte SHA-256 et horodatage RFC 3161 (indispensable)
signtool sign /a /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 MonApp.exe
```

L'option `/a` laisse signtool sélectionner automatiquement le meilleur certificat du
magasin. En CI, on désigne plutôt le certificat par son empreinte, ou on passe par un
fournisseur de clé (KSP) ou un outil connecté à un HSM.

La vérification confirme la signature et la chaîne de confiance.

```powershell
# Politique Authenticode par défaut, en mode verbeux
signtool verify /pa /v MonApp.exe

# Ou en PowerShell, pratique dans un script de contrôle
Get-AuthenticodeSignature .\MonApp.exe | Format-List Status, SignerCertificate
```

En CI, le principe est simple : la clé ne quitte jamais le matériel. Plutôt que de
manipuler un certificat, on délègue la signature à un service qui garde la clé dans
un HSM. **[Azure Trusted Signing][trusted-signing]** (le service de signature cloud de Microsoft) ou
**AzureSignTool** avec une clé dans Azure Key Vault sont les approches courantes. Le
pipeline appelle le service, qui signe et horodate, sans jamais exposer de clé
privée. Les certificats de Trusted Signing sont d'ailleurs à durée de vie très
courte, ce qui rend l'horodatage encore plus vital.

Point utile : la signature ne dépend pas du langage. Que votre binaire vienne de
C++, Rust, Go ou .NET, on signe le `.exe`, la `.dll` ou le `.msi` produit, de la même
manière.

## Trois choses à savoir

1. Horodatez toujours. Sans `/tr`, vos signatures ont la durée de vie du certificat.
   Avec, elles restent vérifiables des années après son expiration.
2. La clé vit sur du matériel, pas dans un fichier. Token, HSM ou service cloud comme
   Azure Trusted Signing. C'est la règle depuis 2023, et c'est aussi la bonne
   hygiène.
3. Signez tout ce que vous livrez. Pas seulement l'exécutable principal : les DLL,
   les installeurs et les scripts distribués comptent aussi. Un maillon non signé
   suffit à casser la chaîne.

## À retenir

Signer un binaire, c'est lui apposer un expéditeur vérifiable et un sceau qui révèle
toute altération. Trois gestes : signer avec un certificat d'une AC de confiance,
horodater pour que la preuve survive à l'expiration, vérifier avant de faire
confiance. C'est la réponse Windows aux exigences d'intégrité et de mise à jour du
CRA.

---

*Épisode précédent : [Vous ne pouvez pas corriger ce que vous ignorez, SBOM et
VEX](CRA-Dev-01-SBOM-VEX.md).*

[signtool]: https://learn.microsoft.com/en-us/dotnet/framework/tools/signtool-exe
[trusted-signing]: https://learn.microsoft.com/en-us/azure/trusted-signing/
