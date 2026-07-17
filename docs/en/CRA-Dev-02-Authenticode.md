# An unsigned .exe is a parcel with no sender: sign your binaries

> **CRA & Dev #2** · ["CRA & Dev" series](index.md) · Reading time: about 6 min · Windows ·
> Tools: signtool, PowerShell, Azure Trusted Signing

## What the CRA requires

Two requirements meet here. Integrity (Annex I, Part I, point 2, f) wants any
unauthorised modification of a program to be detectable. The secure update mechanism
(point c) wants patches to reach the user without being tampered with along the way.

Code signing answers both. A signed binary is a sealed parcel with a verified sender:
the recipient can confirm it really comes from you and that it wasn't opened in
transit. An unsigned `.exe` arrives anonymous, and nothing tells your installer apart
from a booby-trapped copy.

Signing data is one thing; here we sign the executable itself, with the native
Windows mechanism: **Authenticode**.

> This series presents technical practices that contribute to CRA compliance. On
> their own, they are not enough to demonstrate a product's full compliance.

## The classic trap

Three mistakes, all common.

Signing without timestamping. A signature on its own becomes invalid the day the
certificate expires, and every binary you already shipped flips to "unsigned." The
timestamp freezes the proof that the signature was valid at the moment it was
applied. It then stays valid even after the certificate expires. This is not
optional.

Using a self-signed certificate. It chains to no trusted authority: SmartScreen keeps
warning, and the user still sees a warning. To be recognised, the certificate must
come from a trusted CA.

Putting the private key in the repo or the CI. Since 1 June 2023, the CA/Browser
Forum rules require the private key of a code signing certificate to stay on hardware
(token or HSM, including cloud). A base64-encoded `.pfx` in a CI secret is no longer
compliant, and dangerous anyway.

## The technique: sign, timestamp, verify

Signing is done with [`signtool`][signtool]. The timestamp is provided by the `/tr`
option.

```powershell
# Sign with SHA-256 digest and RFC 3161 timestamp (essential)
signtool sign /a /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 MyApp.exe
```

The `/a` option lets signtool automatically select the best certificate in the store.
In CI, you instead identify the certificate by its thumbprint, or go through a key
storage provider (KSP) or a tool connected to an HSM.

Verification confirms the signature and the chain of trust.

```powershell
# Default Authenticode policy, verbose mode
signtool verify /pa /v MyApp.exe

# Or in PowerShell, handy in a check script
Get-AuthenticodeSignature .\MyApp.exe | Format-List Status, SignerCertificate
```

In CI, the principle is simple: the key never leaves the hardware. Rather than
handling a certificate, you delegate signing to a service that keeps the key in an
HSM. **[Azure Trusted Signing][trusted-signing]** (Microsoft's cloud signing service)
or **AzureSignTool** with a key in Azure Key Vault are the common approaches. The
pipeline calls the service, which signs and timestamps, without ever exposing a
private key. Trusted Signing certificates are also very short-lived, which makes
timestamping even more vital.

Worth noting: signing does not depend on the language. Whether your binary comes from
C++, Rust, Go or .NET, you sign the produced `.exe`, `.dll` or `.msi` the same way.

## Three things to know

1. Always timestamp. Without `/tr`, your signatures last only as long as the
   certificate. With it, they stay verifiable for years after it expires.
2. The key lives on hardware, not in a file. Token, HSM, or a cloud service like
   Azure Trusted Signing. It's the rule since 2023, and it's also good hygiene.
3. Sign everything you ship. Not just the main executable: DLLs, installers and
   distributed scripts count too. One unsigned link is enough to break the chain.

## Takeaway

Signing a binary gives it a verifiable sender and a seal that reveals any tampering.
Three moves: sign with a certificate from a trusted CA, timestamp so the proof
outlives expiration, verify before you trust. It's the Windows answer to the CRA's
integrity and update requirements.

---

*Previous episode: [You can't fix what you don't know you're running, SBOM and
VEX](CRA-Dev-01-SBOM-VEX.md).*

[signtool]: https://learn.microsoft.com/en-us/dotnet/framework/tools/signtool-exe
[trusted-signing]: https://learn.microsoft.com/en-us/azure/trusted-signing/
