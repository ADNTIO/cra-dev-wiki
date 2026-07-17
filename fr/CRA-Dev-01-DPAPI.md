**CRA & Dev #1**

# Ne stockez plus jamais un secret en clair : la DPAPI de Windows

> [Série « CRA & Dev »](Home.md) · Lecture : environ 5 min · Windows · Exemples :
> Rust, Python, .NET · [English](../en/CRA-Dev-01-DPAPI.md)

## Ce que demande le CRA

À partir du 11 décembre 2027, le Cyber Resilience Act
([Règlement (UE) 2024/2847][eu-cra]) s'applique à tout logiciel vendu dans l'UE.
Parmi ses règles : les données sensibles stockées doivent être chiffrées.

En clair, pour un développeur : les identifiants, jetons, clés d'API et autres
secrets que votre application garde sur le poste ne peuvent plus traîner en clair
dans un `config.json` ou une clé de registre. Il faut les chiffrer.

## Le piège classique

Chiffrer, tout le monde sait faire. La vraie question arrive juste après : où
stocke-t-on la clé de chiffrement ? La coder en dur dans le binaire, ou la poser à
côté du fichier chiffré, revient dans les deux cas à laisser la porte ouverte. C'est
le problème numéro un du chiffrement applicatif.

## La technique : laisser Windows gérer la clé

Windows règle ce problème depuis Windows 2000 avec la DPAPI (*Data Protection API*).
Le principe : vous ne gérez aucune clé. Le système dérive une clé à partir du secret
de session de l'utilisateur courant, chiffre à votre place, et ne rend la donnée
qu'au même utilisateur sur la même machine. Il y a deux opérations, `Protect` et
`Unprotect`.

Un paramètre optionnel revient dans les trois exemples : l'entropie. C'est un « sel »
propre à votre application, fourni au chiffrement et réclamé à l'identique au
déchiffrement. Il sert à cloisonner vos secrets de ceux des autres applications du
même utilisateur.

### .NET (C#)

La classe [`ProtectedData`][ms-protecteddata] enveloppe la DPAPI.

```csharp
using System.Security.Cryptography;
using System.Text;

byte[] data    = Encoding.UTF8.GetBytes("token-super-secret");
byte[] entropy = Encoding.UTF8.GetBytes("mon-app-v1");   // sel propre à l'app

// Chiffrer, lié à l'utilisateur courant
byte[] blob = ProtectedData.Protect(data, entropy, DataProtectionScope.CurrentUser);

// 'blob' est un paquet opaque : stockez-le tel quel (fichier, registre, base...)

// Déchiffrer, uniquement dans la session du même utilisateur
byte[] clair = ProtectedData.Unprotect(blob, entropy, DataProtectionScope.CurrentUser);
```

### Python (pywin32)

Le module `win32crypt` expose directement les appels Win32.

```python
import win32crypt  # pip install pywin32

data    = "token-super-secret".encode("utf-8")
entropy = b"mon-app-v1"  # sel propre à l'app

# Chiffrer : CryptProtectData(data, description, entropy, reserved, prompt, flags)
blob = win32crypt.CryptProtectData(data, None, entropy, None, None, 0)

# Déchiffrer : renvoie un tuple (description, données)
_, clair = win32crypt.CryptUnprotectData(blob, entropy, None, None, 0)
print(clair.decode("utf-8"))
```

### Rust (crate `windows-dpapi`)

La crate [`windows-dpapi`][windows-dpapi] offre un wrapper sûr autour de la DPAPI.

```rust
// Cargo.toml : windows-dpapi = "0.1"
use windows_dpapi::{encrypt_data, decrypt_data, Scope};

fn main() -> anyhow::Result<()> {
    let secret  = b"token-super-secret";
    let entropy = b"mon-app-v1"; // sel propre à l'app

    // Chiffrer, lié à l'utilisateur courant
    let blob = encrypt_data(secret, Scope::User, Some(entropy))?;

    // Déchiffrer : même utilisateur, même machine, même entropie
    let clair = decrypt_data(&blob, Scope::User, Some(entropy))?;
    assert_eq!(secret.as_slice(), clair.as_slice());
    Ok(())
}
```

Dans les trois cas, vous n'avez aucune clé à générer, stocker ou faire tourner.
Copié sur une autre machine ou ouvert sous un autre compte, le déchiffrement échoue,
ce qui est exactement le comportement recherché.

## Trois choses à savoir avant de l'utiliser

1. La DPAPI protège contre le vol de fichiers, pas contre un attaquant déjà présent
   dans la session. Un code malveillant qui tourne sous l'identité de la victime
   peut appeler `Unprotect` aussi bien que votre application. On parle de chiffrement
   au repos, pas d'un coffre-fort inviolable.
2. Le scope machine (`LocalMachine` en .NET, `Scope::Machine` en Rust) n'est pas un
   raccourci anodin. Sans session utilisateur, pour un service ou une tâche
   planifiée, n'importe quel processus local peut alors déchiffrer. Réservez-le aux
   serveurs où les utilisateurs non approuvés ne peuvent pas ouvrir de session, et
   jamais pour les données d'un utilisateur sur un poste de travail.
3. Pour un secret à très forte valeur, montez d'un cran. La DPAPI reste logicielle,
   adossée au mot de passe. Pour une clé vraiment critique, préférez une clé ancrée
   dans le TPM (via CNG et le *Microsoft Platform Crypto Provider*), qui ne quitte
   jamais la puce.

## À retenir

Pour la plupart des secrets qu'une application Windows conserve localement, la DPAPI
est la réponse simple : quelques lignes de code, aucune gestion de clé, et un premier
pas concret vers l'exigence de « sécurité dès la conception » du CRA. Il faut juste
l'employer en connaissant son modèle de menace.

---

*Prochain épisode de la série « CRA & Dev » : à venir.*

*Pour aller plus loin (MasterKey, DPAPI-NG, comparaison macOS/Linux, historique
complet), voir l'[article de fond dédié](ressources/DPAPI-Article-de-fond.md).*

[eu-cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=fr
[ms-protecteddata]: https://learn.microsoft.com/en-us/dotnet/standard/security/how-to-use-data-protection
[windows-dpapi]: https://crates.io/crates/windows-dpapi
