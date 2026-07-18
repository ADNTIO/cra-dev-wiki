# Never store a secret in plaintext again: Windows DPAPI

> **CRA & Dev #3** · ["CRA & Dev" series](index.md) · Reading time: about 5 min · Windows · Examples:
> Rust, Python, .NET

## What the CRA requires

From 11 December 2027, most products with digital elements placed on the European
Union market will have to meet the requirements of the Cyber Resilience Act
([Regulation (EU) 2024/2847][eu-cra]). One of them concerns protecting data in a way
that is proportionate to the risks, which often means encrypting sensitive data at
rest.

In plain terms, for a developer: the credentials, tokens, API keys and other secrets
your application keeps on the machine can no longer sit in plaintext in a
`config.json` or a registry key. They have to be encrypted.


## The classic trap

Everyone can encrypt. The real question comes right after: where do you store the
encryption key? Hard-coding it in the binary, or dropping it next to the encrypted
file, both leave the door open. This is the number-one problem of application-level
encryption.

## The technique: let Windows manage the key

Windows has handled this since Windows 2000 with DPAPI (*Data Protection API*). The
principle: you manage no key at all. The system derives a key from the current
user's logon secret, encrypts on your behalf, and only returns the data to the same
user on the same machine. There are two operations, `Protect` and `Unprotect`.

One optional parameter shows up in all three examples: entropy. It's an extra piece
of data required identically at decryption time. A public value hard-coded in the
program only provides limited isolation between applications; to add real protection,
it must itself stay confidential.

### .NET (C#)

The [`ProtectedData`][ms-protecteddata] class wraps DPAPI.

```csharp
using System.Security.Cryptography;
using System.Text;

byte[] data    = Encoding.UTF8.GetBytes("super-secret-token");
byte[] entropy = Encoding.UTF8.GetBytes("my-app-v1");   // entropy: keep it secret for real isolation

// Encrypt, bound to the current user
byte[] blob = ProtectedData.Protect(data, entropy, DataProtectionScope.CurrentUser);

// 'blob' is an opaque package: store it as-is (file, registry, database...)

// Decrypt, only within the same user's session
byte[] clear = ProtectedData.Unprotect(blob, entropy, DataProtectionScope.CurrentUser);
```

### Python (pywin32)

The `win32crypt` module exposes the Win32 calls directly.

```python
import win32crypt  # pip install pywin32

data    = "super-secret-token".encode("utf-8")
entropy = b"my-app-v1"  # entropy: keep it secret for real isolation

# Encrypt: CryptProtectData(data, description, entropy, reserved, prompt, flags)
blob = win32crypt.CryptProtectData(data, None, entropy, None, None, 0)

# Decrypt: returns a (description, data) tuple
_, clear = win32crypt.CryptUnprotectData(blob, entropy, None, None, 0)
print(clear.decode("utf-8"))
```

### Rust (`windows-dpapi` crate)

The [`windows-dpapi`][windows-dpapi] crate provides a safe wrapper around DPAPI.

```rust
// Cargo.toml: windows-dpapi = "0.1"
use windows_dpapi::{encrypt_data, decrypt_data, Scope};

fn main() -> anyhow::Result<()> {
    let secret  = b"super-secret-token";
    let entropy = b"my-app-v1"; // entropy: keep it secret for real isolation

    // Encrypt, bound to the current user
    let blob = encrypt_data(secret, Scope::User, Some(entropy))?;

    // Decrypt: same user, same machine, same entropy
    let clear = decrypt_data(&blob, Scope::User, Some(entropy))?;
    assert_eq!(secret.as_slice(), clear.as_slice());
    Ok(())
}
```

In all three cases, you have no key to generate, store or rotate. Copied to another
machine or opened under another account, decryption fails, which is exactly the
behaviour you want.

## Three things to know before using it

1. DPAPI protects against file theft, not against an attacker already inside the
   session. Malicious code running under the victim's identity can call `Unprotect`
   just as well as your application. This is encryption at rest, not an unbreakable
   vault.
2. Machine scope (`LocalMachine` in .NET, `Scope::Machine` in Rust) is not an
   innocent shortcut. Without a user session, for a service or a scheduled task, any
   local process can then decrypt. Keep it for servers where untrusted users cannot
   log on, and never for a user's data on a workstation.
3. For a very high-value secret, go one level up. DPAPI stays software-based, tied to
   the password. For a truly critical key, prefer a key anchored in the TPM (via CNG
   and the *Microsoft Platform Crypto Provider*), which never leaves the chip.

## Takeaway

For most secrets a Windows application keeps locally, DPAPI is the simple answer: a
few lines of code, no key management, and a concrete first step toward the CRA's
"security by design" requirement. You just need to use it while understanding its
threat model.

---

*Previous episode: [An unsigned .exe is a parcel with no sender, sign your binaries](CRA-Dev-02-Authenticode.md).*

*To go deeper (MasterKey, DPAPI-NG, macOS/Linux comparison, full history), see the
in-depth article (currently French, [English translation pending](ressources/DPAPI-Article-de-fond.md)).*

[eu-cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=en
[ms-protecteddata]: https://learn.microsoft.com/en-us/dotnet/standard/security/how-to-use-data-protection
[windows-dpapi]: https://crates.io/crates/windows-dpapi
