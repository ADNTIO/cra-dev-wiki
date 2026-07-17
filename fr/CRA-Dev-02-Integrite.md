**CRA & Dev #2**

# Faites confiance, mais vérifiez : signer vos données pour prouver qu'on n'y a pas touché

> [Série « CRA & Dev »](Home.md) · Lecture : environ 6 min · Multiplateforme ·
> Exemples : Rust, Python, .NET · [English](../en/CRA-Dev-02-Integrity.md)

## Ce que demande le CRA

Le Cyber Resilience Act ne s'arrête pas à la confidentialité. Il demande aussi de
protéger l'intégrité des données, des commandes, des programmes et des
configurations contre toute manipulation non autorisée (Annexe I, partie I,
point 2, f).

Pour un développeur : une donnée que votre application reçoit, lit sur le disque ou
télécharge doit pouvoir être vérifiée avant d'être utilisée. Un fichier de config,
un message entre deux services, une mise à jour : si quelqu'un l'a modifié en
chemin, vous devez pouvoir le détecter.

> Cette série présente des pratiques techniques qui contribuent à la conformité au
> CRA. Leur mise en œuvre ne suffit pas, à elle seule, à démontrer la conformité
> complète d'un produit.

## Le piège classique

Réflexe fréquent : « je stocke un hash SHA-256 à côté du fichier, et je compare ».
Ça détecte une corruption accidentelle, pas une manipulation volontaire. Un
attaquant qui modifie le fichier recalcule simplement le hash et remplace l'ancien.
Un hash seul ne prouve rien sur l'origine de la donnée.

Deuxième piège, plus subtil : comparer deux empreintes avec `==`. Une comparaison
classique s'arrête au premier octet différent et peut introduire une fuite
temporelle sur le nombre d'octets corrects. Utilisez systématiquement les primitives
de vérification fournies par la bibliothèque, qui évitent cette classe de problème.

Il faut donc un secret dans la boucle. Deux outils selon le cas.

## La technique 1 : le HMAC, quand vous contrôlez les deux bouts

Le HMAC combine la donnée avec une clé secrète partagée. Sans la clé, impossible de
produire un HMAC valide, donc impossible de forger une donnée qui passe la
vérification. C'est le bon choix quand la même partie (ou deux parties de
confiance partageant un secret) produit et vérifie la donnée.

### Python

```python
import hmac, hashlib

key  = b"cle-secrete-partagee"
data = b"contenu à protéger"

# Produire le tag
tag = hmac.new(key, data, hashlib.sha256).digest()

# Vérifier, en temps constant (compare_digest, jamais ==)
attendu = hmac.new(key, data, hashlib.sha256).digest()
assert hmac.compare_digest(tag, attendu)
```

### Rust

```rust
// Cargo.toml : hmac = "0.12", sha2 = "0.10"
use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

fn main() {
    let key  = b"cle-secrete-partagee";
    let data = b"contenu a proteger";

    // Produire le tag
    let mut mac = HmacSha256::new_from_slice(key).unwrap();
    mac.update(data);
    let tag = mac.finalize().into_bytes();

    // Vérifier, en temps constant (verify_slice fait la comparaison sûre)
    let mut check = HmacSha256::new_from_slice(key).unwrap();
    check.update(data);
    assert!(check.verify_slice(&tag).is_ok());
}
```

### .NET (C#)

```csharp
using System.Security.Cryptography;
using System.Text;

byte[] key  = Encoding.UTF8.GetBytes("cle-secrete-partagee");
byte[] data = Encoding.UTF8.GetBytes("contenu à protéger");

// Produire le tag
byte[] tag = new HMACSHA256(key).ComputeHash(data);

// Vérifier, en temps constant (FixedTimeEquals, jamais ==)
byte[] attendu = new HMACSHA256(key).ComputeHash(data);
bool ok = CryptographicOperations.FixedTimeEquals(tag, attendu);
```

## La technique 2 : la signature, quand d'autres doivent seulement vérifier

Si celui qui vérifie ne doit pas pouvoir forger la donnée (le cas d'une mise à jour
distribuée à des clients, par exemple), le secret partagé ne convient plus : chaque
vérificateur pourrait alors signer à votre place. Il faut une signature asymétrique.
Vous signez avec une clé privée, tout le monde vérifie avec la clé publique, et
personne d'autre ne peut produire de signature valide.

Ed25519 est un bon défaut moderne : clés courtes, rapide, sans paramètre à régler.

### Python (bibliothèque `cryptography`)

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

data = b"mise à jour v1.2.3"

# Côté éditeur : signer avec la clé privée
priv = Ed25519PrivateKey.generate()
signature = priv.sign(data)

# Côté client : vérifier avec la seule clé publique (lève une exception si invalide)
pub = priv.public_key()
pub.verify(signature, data)
```

En Rust, la crate [`ed25519-dalek`][ed25519-dalek] fait la même chose ; en .NET, il
faut une bibliothèque externe comme [NSec][nsec] (adossée à libsodium) ou
BouncyCastle, Ed25519 n'étant pas dans la BCL.

## Trois choses à savoir

1. HMAC ou signature, le critère est simple. Si celui qui vérifie a le droit de
   produire la donnée, HMAC suffit et c'est plus rapide. Si le vérificateur ne doit
   pas pouvoir forger (distribution à des tiers, mises à jour), il faut une
   signature.
2. Comparez toujours en temps constant. `hmac.compare_digest`,
   `verify_slice`, `CryptographicOperations.FixedTimeEquals`, jamais `==` ni
   `Equals`.
3. L'intégrité ne remplace pas la confidentialité. Un HMAC ou une signature prouve
   qu'une donnée n'a pas été modifiée, mais ne la cache pas. Si elle est sensible,
   chiffrez-la aussi (voir l'[épisode 1](CRA-Dev-01-DPAPI.md)).

## À retenir

Vérifier l'intégrité, c'est refuser d'utiliser une donnée qu'on n'a pas pu
authentifier. HMAC quand vous tenez les deux bouts, signature quand d'autres doivent
seulement vérifier, et comparaison en temps constant dans les deux cas. Trois
primitives, disponibles partout, pour répondre à l'exigence d'intégrité du CRA.

---

*Épisode précédent : [Ne stockez plus jamais un secret en clair, la DPAPI de
Windows](CRA-Dev-01-DPAPI.md).*

[ed25519-dalek]: https://crates.io/crates/ed25519-dalek
[nsec]: https://nsec.rocks/
