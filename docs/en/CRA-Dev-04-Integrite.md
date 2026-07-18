# Trust, but verify: sign your data to prove nobody tampered with it

> **CRA & Dev #4** · ["CRA & Dev" series](index.md) · Reading time: about 6 min · Cross-platform ·
> Examples: Rust, Python, .NET

## What the CRA requires

The Cyber Resilience Act does not stop at confidentiality. It also requires
protecting the integrity of data, commands, programs and configuration against any
unauthorised manipulation (Annex I, Part I, point 2, f).

For a developer: a piece of data your application receives, reads from disk or
downloads must be verifiable before being used. A config file, a message between two
services, an update: if someone changed it along the way, you need to be able to
detect it.

## The classic trap

A common reflex: "I store a SHA-256 hash next to the file and compare them." That
catches accidental corruption, not deliberate tampering. An attacker who modifies
the file simply recomputes the hash and replaces the old one. A hash alone proves
nothing about the origin of the data.

A second, subtler trap: comparing two digests with `==`. An ordinary comparison stops
at the first differing byte and can leak, through response time, how many bytes are
correct. Always use the verification primitives provided by your library, which avoid
this class of problem.

So you need a secret in the loop. Two tools, depending on the case.

## Technique 1: HMAC, when you control both ends

HMAC combines the data with a shared secret key. Without the key, you cannot produce
a valid HMAC, so you cannot forge data that passes verification. It's the right
choice when the same party (or two trusted parties sharing a secret) both produces
and verifies the data.

### Python

```python
import hmac, hashlib

key  = b"shared-secret-key"
data = b"content to protect"

# Produce the tag
tag = hmac.new(key, data, hashlib.sha256).digest()

# Verify, in constant time (compare_digest, never ==)
expected = hmac.new(key, data, hashlib.sha256).digest()
assert hmac.compare_digest(tag, expected)
```

### Rust

```rust
// Cargo.toml: hmac = "0.12", sha2 = "0.10"
use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

fn main() {
    let key  = b"shared-secret-key";
    let data = b"content to protect";

    // Produce the tag
    let mut mac = HmacSha256::new_from_slice(key).unwrap();
    mac.update(data);
    let tag = mac.finalize().into_bytes();

    // Verify, in constant time (verify_slice does the safe comparison)
    let mut check = HmacSha256::new_from_slice(key).unwrap();
    check.update(data);
    assert!(check.verify_slice(&tag).is_ok());
}
```

### .NET (C#)

```csharp
using System.Security.Cryptography;
using System.Text;

byte[] key  = Encoding.UTF8.GetBytes("shared-secret-key");
byte[] data = Encoding.UTF8.GetBytes("content to protect");

// Produce the tag
byte[] tag = new HMACSHA256(key).ComputeHash(data);

// Verify, in constant time (FixedTimeEquals, never ==)
byte[] expected = new HMACSHA256(key).ComputeHash(data);
bool ok = CryptographicOperations.FixedTimeEquals(tag, expected);
```

## Technique 2: signatures, when others only need to verify

If whoever verifies must not be able to forge the data (the case of an update
distributed to clients, for example), a shared secret no longer works: every
verifier could then sign in your place. You need an asymmetric signature. You sign
with a private key, everyone verifies with the public key, and no one else can
produce a valid signature.

Ed25519 is a good modern default: short keys, fast, no parameter to tune.

### Python (`cryptography` library)

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

data = b"update v1.2.3"

# Publisher side: sign with the private key
priv = Ed25519PrivateKey.generate()
signature = priv.sign(data)

# Client side: verify with the public key only (raises if invalid)
pub = priv.public_key()
pub.verify(signature, data)
```

In Rust, the [`ed25519-dalek`][ed25519-dalek] crate does the same; in .NET, you need
an external library such as [NSec][nsec] (backed by libsodium) or BouncyCastle, since
Ed25519 is not in the BCL.

## Three things to know

1. HMAC or signature, the criterion is simple. If whoever verifies is allowed to
   produce the data, HMAC is enough and faster. If the verifier must not be able to
   forge it (distribution to third parties, updates), you need a signature.
2. Always compare in constant time. `hmac.compare_digest`, `verify_slice`,
   `CryptographicOperations.FixedTimeEquals`, never `==` or `Equals`.
3. Integrity does not replace confidentiality. An HMAC or a signature proves that
   data was not modified, but does not hide it. If it is sensitive, encrypt it too
   (see the [DPAPI episode](CRA-Dev-03-DPAPI.md)).

## Takeaway

Verifying integrity means refusing to use data you could not authenticate. HMAC when
you hold both ends, a signature when others only need to verify, and constant-time
comparison in both cases. Three primitives, available everywhere, to meet the CRA's
integrity requirement.

---

*Previous episode: [Never store a secret in plaintext again, Windows
DPAPI](CRA-Dev-03-DPAPI.md).*

[ed25519-dalek]: https://crates.io/crates/ed25519-dalek
[nsec]: https://nsec.rocks/
