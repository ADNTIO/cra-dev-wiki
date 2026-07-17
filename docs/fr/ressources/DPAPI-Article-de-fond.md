# La DPAPI de Windows : comprendre la brique de chiffrement oubliée du système

## Introduction

La **DPAPI** (*Data Protection API*) est l'un des composants cryptographiques les
plus utilisés de Windows, et pourtant l'un des moins connus. Chaque fois qu'un
navigateur mémorise un mot de passe, qu'un client de messagerie stocke des
identifiants, que Wi-Fi enregistre une clé WPA ou que le Gestionnaire
d'identification garde une session, c'est très souvent la DPAPI qui travaille en
coulisses.

Son principe est volontairement simple : offrir aux développeurs un service de
chiffrement « clé en main », intégré au système d'exploitation, sans qu'ils
aient à manipuler eux-mêmes des clés, des algorithmes ou des vecteurs
d'initialisation. Deux appels de fonction suffisent : un pour protéger une
donnée, un pour la déprotéger. La gestion des clés (dérivation, renouvellement,
sauvegarde, récupération) revient entièrement à Windows.

Ce sujet dépasse la simple curiosité technique : il s'inscrit désormais dans un
cadre réglementaire. Le **Cyber Resilience Act** ([Règlement (UE) 2024/2847][eu-cra],
entré en vigueur le 10 décembre 2024, applicable pour l'essentiel au 11 décembre
2027 ; [synthèse ANSSI][anssi-cra]) impose, dans les exigences essentielles de son
**Annexe I**, de protéger la
**confidentialité et l'intégrité des données** stockées, transmises ou traitées par
un produit comportant des éléments numériques, notamment par du **chiffrement des
données au repos** relevant de l'état de l'art. Pour un éditeur, savoir chiffrer
correctement les secrets qu'une application conserve localement (identifiants,
jetons, clés) n'est plus optionnel. Cet article se veut donc aussi une porte
d'entrée pratique : la DPAPI est l'une des techniques les plus simples pour
**tendre vers une application plus sécurisée** sur Windows, sans réinventer de
cryptographie, et donc pour se rapprocher de ces obligations de « sécurité dès la
conception ».

Cet article retrace l'origine et l'histoire de la DPAPI à partir des sources
primaires, explique son fonctionnement interne, son intérêt et ses cas d'usage,
détaille ses évolutions au fil des versions de Windows (jusqu'à la DPAPI-NG), et
se termine par un exemple concret d'utilisation.

---

## Références et documentation

Les faits techniques de cet article s'appuient sur les sources suivantes :

- **Whitepaper fondateur** : [*Windows Data Protection*][ms-whitepaper], NAI Labs
  (Network Associates), Wesley Griffin, Michael Heyman, David Balenson, David
  Carman, octobre 2001. Document de référence historique, toujours publié par
  Microsoft.
- **Documentation officielle Microsoft Learn** : [`CryptProtectData`][ms-cryptprotect],
  [`CryptUnprotectData`][ms-cryptunprotect], [CNG DPAPI (DPAPI-NG)][ms-cng-dpapi] et
  la classe .NET [`ProtectedData`][ms-protecteddata].
- **Recherche académique** : Jean-Michel Picod & Elie Bursztein,
  [*Reversing DPAPI and Stealing Windows Secrets Offline*][picod-bursztein], Black
  Hat DC 2010 / USENIX WOOT '10. Première rétro-ingénierie publique des structures
  internes et outil DPAPICK.
- **Analyses techniques et sécurité offensive** : Synacktiv,
  [*DPAPI exploitation during pentest and password cracking*][synacktiv]
  (UniverShell 2017) ; TierZero Security,
  [*Windows - Data Protection API (DPAPI)*][tierzero] (2024) ; Passcape,
  [*DPAPI Secrets*][passcape].
- **Encyclopédique** : [*Data Protection API*][wikipedia-dpapi], Wikipedia.

---

## Historique

### 2000 : l'apparition avec Windows 2000

La DPAPI fait son entrée avec **Windows 2000**. L'idée de Microsoft est de fournir
un « service de protection de données au niveau du système d'exploitation »
accessible à tous les processus, sans bibliothèque supplémentaire. À l'époque,
le chiffrement applicatif était réservé aux développeurs maîtrisant la
cryptographie ; la DPAPI démocratise cette capacité en la réduisant à deux
appels de fonction.

### 2001 : le whitepaper de référence

En **octobre 2001**, les NAI Labs (division sécurité de Network Associates)
publient pour Microsoft le document *Windows Data Protection*, seule description
publique et détaillée du fonctionnement interne pendant de nombreuses années. Il
décrit l'architecture autour de **Windows XP** : la *MasterKey*, la dérivation de
clé par mot de passe (PBKDF2 / PKCS #5), le chiffrement Triple-DES, le mécanisme
de sauvegarde par contrôleur de domaine, et le disque de réinitialisation de mot
de passe (PRD). Ce whitepaper reste la source historique de référence.

### 2007 : Windows Vista et le passage à CNG

Avec **Windows Vista** (2007), Microsoft introduit **CNG** (*Cryptography Next
Generation*), une refonte modulaire de la pile cryptographique. Vista renforce les
algorithmes de la DPAPI (voir le tableau d'évolution plus bas) et prépare le
terrain pour les fonctionnalités ultérieures.

### 2012 : Windows 8 et la DPAPI-NG

Avec **Windows 8** (2012), Microsoft étend la DPAPI aux scénarios multi-machines
et cloud avec la **DPAPI-NG** (*Next Generation*, aussi appelée *CNG DPAPI*). Là
où la DPAPI classique était cantonnée à une seule machine et à un seul utilisateur,
la DPAPI-NG permet de protéger un secret « à destination » d'un ensemble de
*principals* (utilisateurs, groupes Active Directory, identifiants web) capables
de le déchiffrer sur d'autres machines après authentification.

---

## À quoi sert la DPAPI et pourquoi c'est intéressant

L'intérêt central de la DPAPI est de **déporter toute la complexité cryptographique
vers le système d'exploitation** :

- **Simplicité** : deux fonctions, `CryptProtectData` et `CryptUnprotectData`. Le
  développeur passe des données en clair et reçoit un *blob* opaque, ou l'inverse.
  Il n'a jamais à choisir d'algorithme, ni à générer ou stocker de clé.
- **Pas de gestion de clé applicative** : c'est là l'essentiel. Le talon d'Achille de
  tout chiffrement applicatif est « où stocke-t-on la clé ? ». La DPAPI résout ce
  problème en dérivant la clé du **secret de connexion de l'utilisateur** (le hash
  de son mot de passe, ou sa carte à puce). L'application n'a aucune clé à gérer.
- **Liaison à l'identité** : par défaut, seul l'utilisateur qui a chiffré une donnée
  (avec ses identifiants de session) peut la déchiffrer. La protection est liée au
  compte, pas à un fichier de clé baladeur.
- **Robustesse cryptographique** : la DPAPI s'appuie sur des primitives éprouvées
  (PBKDF2, Triple-DES puis AES-256, HMAC-SHA), avec intégrité (HMAC) et
  renouvellement automatique des clés.
- **Récupération** : grâce au mécanisme de sauvegarde (contrôleur de domaine ou
  disque de réinitialisation) et à l'historique de mots de passe (CREDHIST), les
  données ne sont pas perdues lors d'un changement ou d'une réinitialisation de mot
  de passe.

C'est pourquoi la DPAPI est massivement utilisée par Windows lui-même et par des
logiciels tiers : mots de passe de Chrome/Edge/Firefox, cookies de session,
Gestionnaire d'identification Windows, clés Wi-Fi, certificats et clés privées
(EFS), identifiants RDP, secrets d'applications .NET, etc.

---

## Fonctionnement interne

### Le point d'entrée : deux fonctions et un blob opaque

Les interfaces publiques font partie de `Crypt32.dll` (elle-même partie de la
CryptoAPI), donc disponibles sur toutes les machines Windows. L'application passe
des données en clair et reçoit un **blob de données protégé** : une structure
opaque qui contient non seulement les données chiffrées, mais aussi tout ce qu'il
faut pour les déchiffrer (identifiant de la MasterKey, aléa, description, HMAC).

Point important : **la DPAPI ne stocke rien**. Elle applique seulement une
protection cryptographique. C'est à l'application de conserver le blob (fichier,
registre, base de données…).

Lors d'un appel, la fonction effectue un **appel RPC local** vers la **LSA** (*Local
Security Authority*), le processus système qui gère la sécurité. Ces RPC ne
transitent jamais par le réseau ; les données restent locales. La LSA effectue le
chiffrement/déchiffrement réel dans son contexte de sécurité, ce qui permet
notamment de générer des audits.

### La MasterKey : le pivot du système

Plutôt que de chiffrer directement les données avec une clé issue du mot de passe,
la DPAPI utilise une clé intermédiaire, la **MasterKey** :

1. La DPAPI génère une **MasterKey** aléatoire (512 bits de données aléatoires, un
   « secret fort » plus qu'une clé au sens strict).
2. Cette MasterKey est protégée par une clé **dérivée du mot de passe de
   l'utilisateur** via **PBKDF2** (PKCS #5) : le mot de passe passe d'abord par
   SHA-1 (le *logon credential*), puis PBKDF2 applique un grand nombre d'itérations
   avec un sel de 16 octets aléatoires.
3. La clé dérivée sert à **chiffrer** la MasterKey (Triple-DES à l'origine, AES-256
   sur les versions modernes), avec un **HMAC** pour garantir l'intégrité.
4. La MasterKey chiffrée, le sel et le nombre d'itérations sont stockés dans un
   **fichier MasterKey** dans le profil utilisateur.

Emplacement des fichiers MasterKey :

```
%APPDATA%\Microsoft\Protect\{SID}\
```

où `{SID}` est l'identifiant de sécurité de l'utilisateur. Le dossier contient un
fichier par MasterKey (nommé par un GUID) et un fichier `Preferred` qui pointe vers
la MasterKey courante. Ces éléments sont cachés (`dir /a` pour les lister).

Pour les comptes systèmes (LOCAL SERVICE, NETWORK SERVICE, SYSTEM), les MasterKeys
sont dans `C:\Windows\System32\Microsoft\Protect\S-1-5-18` et sont protégées non pas
par un mot de passe utilisateur mais par le secret LSA **DPAPI_SYSTEM**, lui-même
dérivé de la *BootKey* du système.

### La clé de session : la vraie clé de chiffrement

La MasterKey ne chiffre jamais directement les données. Pour chaque opération de
protection :

1. 16 octets aléatoires sont générés puis hachés (SHA-1) avec la MasterKey.
2. On y ajoute l'**entropie optionnelle** fournie par l'application et un éventuel
   mot de passe utilisateur.
3. Le résultat est passé à `CryptDeriveKey`, qui produit la **clé de session**
   symétrique.
4. C'est cette clé de session qui chiffre les données. **Elle n'est jamais stockée** :
   seuls les octets aléatoires nécessaires à la re-dérivation sont conservés dans
   le blob (protégés en intégrité par HMAC).

### L'entropie secondaire : cloisonner les applications

Puisque toutes les applications d'un même utilisateur partagent la même MasterKey,
n'importe laquelle pourrait théoriquement déchiffrer les données d'une autre. Pour
limiter cela, une application peut fournir une **entropie secondaire** (un secret
propre) au moment du chiffrement ; le **même secret** sera exigé au déchiffrement.
Attention : mal protégée (stockée en clair à côté du blob), cette entropie perd
tout son intérêt.

### Expiration et historique des mots de passe

- **Expiration** : pour limiter l'impact d'une compromission, les MasterKeys
  expirent (valeur historique codée en dur : **3 mois**). Une nouvelle MasterKey est
  alors générée. Les anciennes ne sont **jamais supprimées** (sinon les vieux blobs
  seraient illisibles) : le GUID de la MasterKey ayant servi est stocké dans chaque
  blob pour retrouver la bonne.
- **Changement de mot de passe** : la DPAPI se greffe sur le module de changement
  de mot de passe : toutes les MasterKeys sont re-chiffrées sous le nouveau mot de
  passe. En complément, le fichier **CREDHIST** (*Credential History*) conserve
  l'historique des anciens mots de passe (chaîne chiffrée en cascade), ce qui permet
  de remonter aux anciennes clés si nécessaire. Les comptes de domaine n'utilisent
  pas de CREDHIST.

### Sauvegarde et récupération

- **En domaine** : à la création d'une MasterKey, le client DPAPI récupère la **clé
  publique RSA du contrôleur de domaine** (dédiée à la DPAPI) via un RPC
  mutuellement authentifié et chiffré, puis chiffre une copie de sauvegarde de la
  MasterKey avec cette clé publique. En cas d'échec du déchiffrement par le mot de
  passe (ex. réinitialisation administrateur), le client envoie cette sauvegarde au
  DC qui la déchiffre avec sa clé privée. Ce **Domain Backup Key** est un mécanisme
  central : quiconque possède la clé privée de sauvegarde du domaine peut déchiffrer
  la DPAPI de **tous** les utilisateurs du domaine.
- **En poste isolé / workgroup** : le **disque de réinitialisation de mot de passe**
  (PRD, introduit avec Windows XP) génère une paire RSA 2048 bits : le mot de passe
  courant est chiffré avec la clé publique (stockée dans le profil), la clé privée
  étant conservée hors machine sur le support amovible.

---

## Protection au niveau machine (scope machine)

Tout ce qui précède décrit le mode par défaut : une protection **liée à
l'utilisateur**, dérivée de son secret de connexion. Mais la DPAPI possède un
second mode, essentiel en pratique : la protection **au niveau machine**, qui ne
dépend d'aucun utilisateur.

### Le drapeau `CRYPTPROTECT_LOCAL_MACHINE`

Au moment du chiffrement, une application peut passer le drapeau
**`CRYPTPROTECT_LOCAL_MACHINE`** (en .NET : `DataProtectionScope.LocalMachine`).
La donnée est alors liée à la **machine** et non à un compte : **n'importe quel
processus s'exécutant sur cette machine** peut la déprotéger, quel que soit
l'utilisateur.

C'est indispensable pour tout ce qui doit être déchiffré **sans session
utilisateur interactive** : services Windows, tâches planifiées, pools
d'applications IIS, agents et démons. Ces composants tournent sous des comptes
systèmes (SYSTEM, LOCAL SERVICE, NETWORK SERVICE) ou de service, souvent avant
qu'un utilisateur ne se connecte.

Le whitepaper de 2001 insiste toutefois sur un point de sécurité : dans ce mode,
la DPAPI n'apporte « aucune protection réelle » vis-à-vis des utilisateurs locaux,
puisque tout processus de la machine peut déchiffrer. Il ne faut donc **jamais**
l'utiliser pour protéger des données propres à un utilisateur sur un poste de
travail. Il est en revanche justifié sur un serveur où les utilisateurs non
approuvés ne peuvent pas ouvrir de session, ou pour des données destinées à être
stockées hors machine.

### Les MasterKeys machine et le secret DPAPI_SYSTEM

La protection machine repose sur ses propres MasterKeys, stockées séparément de
celles des utilisateurs :

```
C:\Windows\System32\Microsoft\Protect\S-1-5-18\        (MasterKeys « machine »,
                                                        pour le flag LOCAL_MACHINE)
C:\Windows\System32\Microsoft\Protect\S-1-5-18\User\   (MasterKeys des comptes de
                                                        service : LOCAL/NETWORK SERVICE)
```

Ces MasterKeys ne peuvent pas être protégées par un mot de passe utilisateur
(il n'y en a pas). Elles sont chiffrées à l'aide du **secret LSA `DPAPI_SYSTEM`**,
stocké dans le registre sous
`HKEY_LOCAL_MACHINE\SECURITY\Policy\Secrets`, lui-même dérivé de la **BootKey**
(clé d'amorçage) du système. Ce secret `DPAPI_SYSTEM` n'est accessible qu'au
compte **SYSTEM** ; il comporte en réalité deux parties, l'une servant aux
MasterKeys machine, l'autre aux MasterKeys des comptes de service.

### Ce que protège la DPAPI machine

En pratique, c'est la DPAPI machine qui protège une grande partie des secrets du
système lui-même :

- mots de passe des **tâches planifiées** et des **services** ;
- identifiants de comptes de service, secrets de pools d'applications **IIS** ;
- certaines **clés Wi-Fi** enregistrées au niveau machine ;
- des clés sensibles côté serveur, par exemple les **clés de signature ADFS**
  (protégées via un mécanisme DKM adossé à la DPAPI machine).

### Implication de sécurité

Le modèle de menace est différent du mode utilisateur. Ici, la protection ne
repose pas sur un mot de passe mais sur un secret (`DPAPI_SYSTEM`) accessible au
compte SYSTEM. **Quiconque obtient les privilèges SYSTEM sur la machine** (ou une
copie hors ligne des ruches `SYSTEM` et `SECURITY`) peut reconstituer
`DPAPI_SYSTEM`, déchiffrer les MasterKeys machine, puis tous les secrets protégés
au niveau machine, sans jamais connaître le moindre mot de passe utilisateur.
C'est ce que font des commandes comme `machinemasterkeys` de SharpDPAPI. En
passant de la DPAPI utilisateur à la DPAPI machine, on déplace le point de
confiance du **mot de passe de l'utilisateur** vers le **contrôle du compte
SYSTEM**.

---

## Évolution des algorithmes au fil des versions

L'un des points les plus concrets de l'évolution de la DPAPI concerne les
algorithmes de protection de la MasterKey, renforcés au fil des versions :

| Version de Windows | Chiffrement MasterKey | HMAC / hachage | Itérations PBKDF2 |
| --- | --- | --- | --- |
| Windows 2000 / XP | Triple-DES (CBC) | SHA-1 | 4 000 (min., ajustable via `MasterKeyIterationCount`) |
| Windows Vista | Triple-DES (CBC) | HMAC-SHA-1 | 24 000 |
| Windows 7 / 8 / 10 / 11 | AES-256 (CBC) | HMAC-SHA-512 | ~5 600 |

*(Sources : [whitepaper NAI Labs 2001][ms-whitepaper] ;
[présentation Synacktiv UniverShell 2017][synacktiv] ; analyses
[Passcape][passcape] et [TierZero][tierzero].)*

À partir de **Windows 8**, les fournisseurs CNG s'imposent, garantissant l'usage
d'AES-256 pour les nouvelles protections et abandonnant les options héritées plus
faibles (3DES). Le nombre d'itérations PBKDF2 a lui aussi été relevé au fil du
temps pour augmenter le coût d'une attaque par force brute sur le mot de passe.

---

## La DPAPI-NG (CNG DPAPI)

La **DPAPI-NG**, introduite avec **Windows 8 / Windows Server 2012**, répond à une
limite structurelle de la DPAPI classique : celle-ci est **liée à une seule machine
et à un seul utilisateur**. Or le cloud et les architectures distribuées imposent
souvent de chiffrer une donnée sur une machine et de la déchiffrer sur une autre.

La DPAPI-NG permet de **protéger un secret à destination d'un ensemble de
*principals*** :

- un **groupe d'une forêt Active Directory** ;
- des **identifiants web** (web credentials) ;
- un **SID**, une **clé/certificat**, ou le principal local (`LOCAL=user`,
  `LOCAL=machine`).

Ces cibles sont décrites par des **descripteurs de protection** au format SDDL
(ex. `SID=S-1-5-...`). N'importe quel principal autorisé peut, après
authentification et autorisation, retirer la protection, y compris sur une autre
machine du domaine.

Techniquement, la DPAPI-NG repose sur **CNG** et expose de nouvelles fonctions,
notamment :

- `NCryptCreateProtectionDescriptor` / `NCryptCloseProtectionDescriptor`
- `NCryptProtectSecret` / `NCryptUnprotectSecret`
- les fonctions de flux `NCryptStreamOpenToProtect` / `...ToUnprotect` / `...Update`

C'est la DPAPI-NG qui est utilisée en interne, par exemple, par le chiffrement des
clés « au repos » d'ASP.NET Core (`ProtectKeysWithDpapiNG`) ou par des solutions de
partage de secrets en environnement Active Directory.

### Disponibilité : depuis Windows 8, et non Windows 11

La DPAPI-NG **n'est pas spécifique à Windows 11**. La source est la documentation
Microsoft officielle : la page [*CNG DPAPI*][ms-cng-dpapi] de Microsoft Learn
indique explicitement : « *beginning with Windows 8, Microsoft extended the idea of
using a relatively straightforward API to encompass cloud scenarios. This new API,
called DPAPI-NG...* ».

Les fonctions `NCryptProtectSecret` / `NCryptUnprotectSecret` et
l'ensemble des descripteurs de protection existent donc depuis **Windows 8 et Windows
Server 2012**. On les retrouve à l'identique sur **Windows 10** comme sur
**Windows 11** : Windows 11 n'a rien introduit de nouveau sur ce plan. La confusion
vient probablement du fait que la DPAPI-NG reste peu utilisée directement par les
développeurs et souvent masquée derrière des couches de plus haut niveau (ASP.NET
Core Data Protection, PowerShell SecretManagement…).

### Windows 10 vs Windows 11 : qu'est-ce qui change réellement ?

Au niveau de la DPAPI elle-même : **rien de fondamental**. L'architecture
(MasterKey, clé de session, DPAPI-NG) et les algorithmes (AES-256-CBC /
HMAC-SHA-512, PBKDF2) sont **identiques** entre Windows 10 et Windows 11. Un blob
DPAPI produit sous Windows 10 est déchiffrable sous Windows 11 et réciproquement,
à secret équivalent.

Les différences se situent dans l'**écosystème de sécurité autour** de la DPAPI, où
Windows 11 (notamment la version **24H2**) a renforcé plusieurs points connexes :

- **LSA Protection activée par défaut** : après une phase d'audit, Windows 11 24H2
  active automatiquement la protection du processus LSASS (empêchant le chargement
  de code non signé et le *dump* mémoire). Or c'est précisément dans LSASS que les
  MasterKeys DPAPI déchiffrées transitent : leur extraction en mémoire (technique
  classique de mimikatz) en devient nettement plus difficile.
- **SHA-3 dans CNG** : Windows 11 24H2 ajoute la famille SHA-3 (SHA3-256/384/512,
  SHAKE, cSHAKE, KMAC) à la bibliothèque CNG. La DPAPI ne l'emploie pas
  aujourd'hui, mais cela enrichit le socle CNG sur lequel repose la DPAPI-NG.
- **Personal Data Encryption (PDE)** : un mécanisme *distinct* de la DPAPI, adossé à
  Windows Hello, qui chiffre le contenu des dossiers connus (Documents, Bureau,
  Images) avec des clés libérées par l'authentification biométrique. À ne pas
  confondre avec la DPAPI, mais il illustre la direction prise : lier la protection
  des données à une authentification forte plutôt qu'au seul mot de passe.

Si l'on parle strictement de la DPAPI, Windows 10 et Windows 11
sont donc équivalents ; les écarts pertinents concernent le durcissement de LSASS
et les mécanismes voisins, qui rendent l'**extraction** des secrets plus difficile
sous Windows 11 sans changer la DPAPI en tant que telle.

---

## Aspects sécurité : ce que la DPAPI protège... et ne protège pas

La DPAPI offre une bonne sécurité **compte tenu du fait qu'elle repose sur le mot
de passe de l'utilisateur**. Le whitepaper de 2001 était déjà lucide : « la DPAPI
n'est pas infaillible à 100 % ». Les points d'attention, confirmés par la recherche
ultérieure, sont :

- **La protection vaut celle du secret de connexion.** Toute la sécurité repose sur
  le mot de passe (ou la carte à puce). Un mot de passe faible = une DPAPI faible.
- **Attaques hors ligne** : en 2010, Jean-Michel Picod et Elie Bursztein ont
  publiquement rétro-conçu les structures de la DPAPI (Black Hat DC 2010, USENIX
  WOOT) et publié **DPAPICK**, premier outil de déchiffrement **hors ligne**. Dès
  lors qu'un attaquant récupère les fichiers MasterKey et connaît (ou casse) le mot
  de passe, il peut déchiffrer les blobs sur une autre machine.
- **Le contexte utilisateur suffit** : un code malveillant s'exécutant sous
  l'identité de la victime peut appeler `CryptUnprotectData` exactement comme
  l'application légitime. La DPAPI protège contre le **vol de fichiers**, pas contre
  un attaquant déjà présent dans la session.
- **Extraction en mémoire** : des outils comme **mimikatz** extraient les MasterKeys
  déchiffrées directement de la mémoire de **LSASS**, ou forgent des MasterKeys.
- **La clé de sauvegarde de domaine est un secret critique** : quiconque compromet
  la clé privée de sauvegarde DPAPI d'un contrôleur de domaine peut déchiffrer les
  secrets DPAPI de **tous les utilisateurs du domaine**. C'est une cible de choix en
  post-exploitation Active Directory.
- **`CRYPTPROTECT_LOCAL_MACHINE`** : ce drapeau lie la donnée à la machine plutôt
  qu'à l'utilisateur : **tout** processus de la machine peut alors déchiffrer. Le
  whitepaper insiste : cela ne fournit « aucune protection réelle » vis-à-vis des
  utilisateurs locaux, et ne doit pas servir à protéger des données utilisateur sur
  un poste de travail.

Outils couramment cités dans ce domaine (recherche / audit / red team) :
**DPAPICK**, **mimikatz**, **SharpDPAPI** (GhostPack), **Impacket** (`dpapi.py`),
**hashcat/John** pour casser les mots de passe des MasterKeys.

> **Note de contexte.** Ces outils et techniques relèvent de l'analyse forensique,
> de l'audit de sécurité et du test d'intrusion **autorisés**. Ils sont rappelés
> ici pour comprendre le modèle de menace de la DPAPI, pas pour un usage offensif
> non consenti.

---

## Exemple pratique

### 1. En PowerShell / .NET : protection liée à l'utilisateur

Le plus simple pour manipuler la DPAPI est la classe .NET
`System.Security.Cryptography.ProtectedData`, qui enveloppe `CryptProtectData` /
`CryptUnprotectData`. Le `DataProtectionScope` correspond au choix
utilisateur (`CurrentUser`) ou machine (`LocalMachine`).

```powershell
Add-Type -AssemblyName System.Security

# --- Données à protéger et entropie optionnelle (secret propre à l'app) ---
$secret  = "Mot de passe très confidentiel"
$bytes   = [System.Text.Encoding]::UTF8.GetBytes($secret)
$entropy = [System.Text.Encoding]::UTF8.GetBytes("mon-entropie-applicative")

# --- Protection (liée à l'utilisateur courant) ---
$protected = [System.Security.Cryptography.ProtectedData]::Protect(
    $bytes,
    $entropy,
    [System.Security.Cryptography.DataProtectionScope]::CurrentUser
)

# Le blob opaque peut être stocké tel quel (ici en Base64)
$blobB64 = [Convert]::ToBase64String($protected)
Write-Host "Blob protégé (Base64) : $blobB64"

# --- Déprotection (nécessite la même entropie ET la même session utilisateur) ---
$unprotected = [System.Security.Cryptography.ProtectedData]::Unprotect(
    [Convert]::FromBase64String($blobB64),
    $entropy,
    [System.Security.Cryptography.DataProtectionScope]::CurrentUser
)

$clair = [System.Text.Encoding]::UTF8.GetString($unprotected)
Write-Host "Déchiffré : $clair"
```

Points à retenir sur cet exemple :

- Le `Unprotect` ne réussira que **dans la session du même utilisateur** (scope
  `CurrentUser`) et **avec la même entropie**. Copié sur une autre machine ou lancé
  sous un autre compte, il échouera, ce qui est exactement la propriété recherchée.
- L'application ne voit **jamais** de clé : tout est géré par Windows via la
  MasterKey de l'utilisateur.

### 2. En C# : l'équivalent typé

```csharp
using System;
using System.Text;
using System.Security.Cryptography;

class DpapiDemo
{
    static void Main()
    {
        byte[] data    = Encoding.UTF8.GetBytes("Mot de passe très confidentiel");
        byte[] entropy = Encoding.UTF8.GetBytes("mon-entropie-applicative");

        // Protection liée à l'utilisateur courant
        byte[] blob = ProtectedData.Protect(
            data, entropy, DataProtectionScope.CurrentUser);

        Console.WriteLine("Blob : " + Convert.ToBase64String(blob));

        // Déprotection
        byte[] clear = ProtectedData.Unprotect(
            blob, entropy, DataProtectionScope.CurrentUser);

        Console.WriteLine("Clair : " + Encoding.UTF8.GetString(clear));
    }
}
```

### 3. Variante : protection au niveau machine

Pour un secret devant être déchiffré par un service ou une tâche planifiée, sans
session utilisateur, on utilise le scope machine. Il suffit de remplacer
`CurrentUser` par `LocalMachine` :

```powershell
Add-Type -AssemblyName System.Security

$bytes = [System.Text.Encoding]::UTF8.GetBytes("secret de service")

# Protection liée à la MACHINE : déchiffrable par tout processus de cette machine
$protected = [System.Security.Cryptography.ProtectedData]::Protect(
    $bytes, $null,
    [System.Security.Cryptography.DataProtectionScope]::LocalMachine
)
# ... Unprotect avec le même scope LocalMachine, dans n'importe quelle session.
```

À n'utiliser **que** sur un hôte où les utilisateurs non approuvés ne peuvent pas
ouvrir de session (typiquement un serveur applicatif) : rappelons qu'en scope
machine, n'importe quel processus local peut déprotéger la donnée.

### 4. Aperçu de la DPAPI-NG : protection à destination d'un groupe AD

Là où la DPAPI classique est mono-machine, la DPAPI-NG permet de cibler un
*principal* (ici, tous les membres d'un groupe Active Directory identifié par son
SID), de sorte que n'importe quel membre autorisé puisse déchiffrer, y compris sur
une autre machine du domaine :

```powershell
# Nécessite un module exposant NCryptProtectSecret (ex. jborean93/SecretManagement.DpapiNG)
# Descripteur de protection : "à destination du groupe AD S-1-5-21-...-512"
$descriptor = "SID=S-1-5-21-1234567890-123456789-1234567890-512"

# Le secret protégé est déchiffrable par tout principal correspondant au descripteur,
# sur n'importe quelle machine du domaine, après authentification.
```

Ce déplacement, d'une protection liée à **une machine et un utilisateur** vers une
protection liée à **une identité de domaine partageable**, résume bien la
trajectoire de la DPAPI en un quart de siècle : d'un simple service local de
confidentialité (Windows 2000) à une brique de partage de secrets pour
environnements distribués et cloud (DPAPI-NG).

---

## Au-delà de la DPAPI : les mécanismes plus récents de Windows

La DPAPI n'a pas été remplacée, elle reste omniprésente, mais Windows l'a
progressivement **complétée** par des mécanismes qui corrigent sa principale
faiblesse : le fait de reposer, en dernier ressort, sur un secret **logiciel**
(mot de passe utilisateur ou secret `DPAPI_SYSTEM`) extractible par un attaquant
suffisamment privilégié. La tendance de fond est claire : **ancrer les secrets
dans du matériel** (TPM) et **isoler** leur manipulation du système d'exploitation.

- **TPM et clés CNG adossées au matériel** : via CNG et le KSP *Microsoft Platform
  Crypto Provider*, une clé peut être générée **dans le TPM** et ne jamais en
  sortir en clair. Contrairement à une MasterKey DPAPI, la clé privée n'existe pas
  sur le disque sous une forme déchiffrable hors de la puce.
- **Windows Hello for Business** : remplace le mot de passe par une **paire de clés
  asymétrique protégée par le TPM**, débloquée par un geste local (PIN ou
  biométrie). Le TPM apporte l'*anti-hammering* (limitation des tentatives de PIN)
  et le secret n'est jamais transmis sur le réseau. C'est un changement de paradigme
  par rapport à la protection logicielle de la DPAPI.
- **Credential Guard / VBS** : la *Virtualization-Based Security* isole les secrets
  d'authentification (hashes NTLM, tickets Kerberos) dans un environnement
  virtualisé (LSAIso) inaccessible même au noyau Windows. Objectif : rendre
  inopérantes les techniques d'extraction mémoire type mimikatz.
- **Personal Data Encryption (PDE)** : introduit récemment (Windows 11), il chiffre
  des dossiers utilisateur avec des clés libérées par **Windows Hello**, plutôt que
  par le seul secret de session. Mécanisme distinct de la DPAPI, mais qui illustre
  la même direction : lier la donnée à une authentification forte.
- **Passkeys / FIDO2** : pour l'authentification, Windows pousse les clés d'accès
  (passkeys) stockées dans le TPM ou un authentificateur matériel, ce qui élimine le
  mot de passe partagé, et donc la dépendance qui fait la fragilité de la DPAPI.

Pour résumer, la DPAPI reste l'outil de base du chiffrement au repos côté
applications, mais tout ce qui touche à l'**authentification** et aux **secrets à
haute valeur** migre vers des clés **ancrées dans le TPM** et **isolées par la
virtualisation**.

---

## Similitudes avec macOS et Linux

Le problème que résout la DPAPI, à savoir *« comment une application chiffre-t-elle
un secret sans avoir à gérer elle-même une clé ? »*, est universel. macOS et Linux y
répondent avec des architectures très proches dans l'esprit.

### macOS : le Trousseau (Keychain) et la Secure Enclave

Le **[Keychain][apple-keychain]** est l'équivalent le plus direct de la DPAPI, en
plus riche :

- **Même principe de dérivation par identité** : chaque élément est chiffré par une
  clé par-item, elle-même enveloppée par une *class key* protégée par les
  identifiants de session de l'utilisateur. On retrouve exactement la logique de la
  DPAPI, où la MasterKey sert à dériver la clé de session.
- **Différence majeure, l'ancrage matériel** : sur les Mac récents (puces Apple),
  les *class keys* sont protégées par la **Secure Enclave**, un coprocesseur dédié
  avec sa propre racine de confiance. C'est ce que la DPAPI *classique* ne fait pas
  (elle est purement logicielle) et que Windows ne rattrape qu'avec le TPM et
  Windows Hello.
- **Contrôle d'accès plus fin** : le Keychain associe des ACL par élément
  (quelle application, quelle condition d'authentification Touch ID/Face ID), là où
  la DPAPI se contente d'une entropie secondaire optionnelle.
- Sur iOS, la *Data Protection* lie de surcroît les clés à l'état verrouillé/
  déverrouillé de l'appareil (classes de protection), un raffinement que la DPAPI
  n'a pas.

### Linux : le Secret Service, les Keyrings et le TPM

Linux n'a pas d'API unique intégrée au noyau, mais un **empilement de briques** qui,
ensemble, jouent le même rôle :

- **Secret Service API (D-Bus)** : la norme commune, implémentée par
  **[GNOME Keyring][arch-gnome-keyring]** et **KWallet** (KDE). L'API `libsecret` en
  est le client. Comme la
  DPAPI, le trousseau par défaut (`login.keyring`) est **déverrouillé
  automatiquement à l'ouverture de session**, sa clé étant dérivée du mot de passe
  de connexion : le parallèle avec la MasterKey DPAPI est direct.
- **Kernel keyring** (`keyctl`, `keyutils`) : un stockage de clés en mémoire géré
  par le noyau, avec des trousseaux par thread/processus/session. Plus proche, sur
  le principe, du stockage volatil de la clé de session DPAPI dans LSASS.
- **[systemd-creds][systemd-creds]** : l'équivalent le plus fidèle de la **DPAPI
  machine**. Il chiffre des secrets destinés aux services système, en s'appuyant si
  possible sur
  le **TPM 2.0** (et une clé hôte). C'est le pendant du couple
  `CRYPTPROTECT_LOCAL_MACHINE` / `DPAPI_SYSTEM`, mais avec un ancrage TPM d'emblée.

### Ce que la comparaison révèle

Les trois systèmes convergent sur le même schéma :

| Concept | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Coffre lié à la session utilisateur | DPAPI (MasterKey) | Keychain | GNOME Keyring / KWallet |
| Déverrouillage auto à l'ouverture de session | oui (mot de passe) | oui | oui (`login.keyring`) |
| Secrets niveau machine/service | DPAPI machine + `DPAPI_SYSTEM` | System Keychain | `systemd-creds` |
| Ancrage matériel | TPM (via CNG / Hello), tardif | Secure Enclave, natif | TPM 2.0 (via `systemd-creds`) |
| Stockage volatil de clé de session | LSASS | securityd | kernel keyring |

La grande leçon est que la DPAPI, conçue en 2000, était **en avance** sur son idée
directrice (déporter la crypto vers l'OS et la lier à l'identité), mais **en retard**
sur l'ancrage matériel : macOS l'a intégré nativement avec la Secure Enclave, Linux
l'adopte via le TPM et `systemd-creds`, et Windows comble l'écart avec le TPM,
Windows Hello et Credential Guard.

---

## Bilan de l'évolution et perspectives d'avenir

### La trajectoire en un coup d'œil

En un quart de siècle, la DPAPI a suivi une trajectoire cohérente, du service
local minimal vers une brique intégrée à un écosystème de sécurité matériel :

| Année | Version | Apport majeur |
| --- | --- | --- |
| 2000 | Windows 2000 | Naissance de la DPAPI : chiffrement au niveau OS lié au mot de passe |
| 2001 | Windows XP | Whitepaper de référence ; disque de réinitialisation (PRD) |
| 2007 | Windows Vista | Passage à CNG ; renforcement des algorithmes |
| ~2009 | Windows 7 | MasterKey en AES-256-CBC / HMAC-SHA-512 |
| 2012 | Windows 8 / Server 2012 | **DPAPI-NG** : partage de secrets multi-machines, principals AD |
| 2015+ | Windows 10 | Stabilisation ; essor du TPM, Windows Hello, Credential Guard *autour* de la DPAPI |
| 2021+ | Windows 11 | Durcissement de l'environnement (LSA protection par défaut en 24H2, PDE, SHA-3 dans CNG) |

Le cœur de la DPAPI (MasterKey servant à dériver la clé de session, sauvegarde par
domaine, CREDHIST) est resté **remarquablement stable** depuis 2001. Ce qui a changé, c'est
l'environnement : algorithmes renforcés, ouverture au multi-machine (DPAPI-NG), et
surtout apparition de mécanismes **complémentaires** ancrés dans le matériel.

### Sa limite structurelle

La principale limite de la DPAPI est aussi sa principale force : la protection est
**liée à un secret logiciel** (mot de passe utilisateur, ou secret `DPAPI_SYSTEM`
pour le mode machine). Cela la rend transparente et récupérable, mais signifie
qu'un attaquant qui obtient le contexte de l'utilisateur, les privilèges SYSTEM, ou
la clé de sauvegarde du domaine, obtient aussi les secrets. C'est ce qui a motivé
l'ajout, par-dessus, du TPM, de Windows Hello et de Credential Guard.

### L'avenir

Trois tendances se dessinent :

- **L'ancrage matériel devient la norme.** Les secrets les plus sensibles migrent
  vers des clés générées dans le **TPM** (ou la Secure Enclave côté Apple, le TPM
  côté Linux via `systemd-creds`), qui ne quittent jamais la puce en clair. La DPAPI
  purement logicielle est peu à peu réservée aux secrets « ordinaires ».
- **La fin du mot de passe partagé.** Passkeys/FIDO2 et Windows Hello for Business
  suppriment le secret réutilisable dont dépend la DPAPI. À terme, la protection des
  données tend à être libérée par une **authentification forte** (biométrie, PIN
  local) plutôt que par un hash de mot de passe.
- **La pression réglementaire.** Avec le **Cyber Resilience Act** (application au
  11 décembre 2027), le chiffrement des données au repos « à l'état de l'art »
  devient une exigence légale pour les produits numériques vendus dans l'UE. La
  DPAPI reste une réponse simple et légitime pour un éditeur Windows, à condition
  d'en connaître le modèle de menace et de la combiner, pour les secrets à forte
  valeur, avec un ancrage matériel.

La DPAPI ne va donc pas disparaître : elle restera l'outil de référence du
chiffrement au repos côté applications. Mais elle s'inscrit désormais dans une pile
de sécurité plus large, où le point de confiance se déplace du **mot de passe** vers
le **matériel**. Comprendre à la fois ce qu'elle protège et ce qu'elle ne protège
pas reste essentiel, aussi bien pour les développeurs qui s'en servent comme premier
pas vers une application plus sûre que pour les équipes défensives qui doivent la
surveiller.

---

## Bibliographie

1. NAI Labs (W. Griffin, M. Heyman, D. Balenson, D. Carman),
   [*Windows Data Protection*][ms-whitepaper], octobre 2001, Microsoft Learn
   (archive).
2. Microsoft Learn, [*CryptProtectData*][ms-cryptprotect] /
   [*CryptUnprotectData*][ms-cryptunprotect].
3. Microsoft Learn, [*CNG DPAPI (DPAPI-NG)*][ms-cng-dpapi].
4. Microsoft Learn, [*How to: Use Data Protection (.NET ProtectedData)*][ms-protecteddata].
5. J.-M. Picod & E. Bursztein,
   [*Reversing DPAPI and Stealing Windows Secrets Offline*][picod-bursztein],
   Black Hat DC 2010 / USENIX WOOT '10.
6. Synacktiv, [*DPAPI exploitation during pentest and password cracking*][synacktiv],
   UniverShell 2017.
7. TierZero Security, [*Windows - Data Protection API (DPAPI)*][tierzero], 2024.
8. Passcape, [*DPAPI Secrets - Security analysis and data recovery in DPAPI*][passcape].
9. Wikipedia, [*Data Protection API*][wikipedia-dpapi].
10. Microsoft Learn,
    [*What's new in Windows 11, version 24H2 for IT pros*][ms-win11-24h2] (LSA
    protection, SHA-3, PDE).
11. Microsoft Learn, [*Credential Guard*][ms-credential-guard] et
    [*Windows Hello for Business FAQ*][ms-hello].
12. Union européenne, [*Règlement (UE) 2024/2847 (Cyber Resilience Act)*][eu-cra],
    EUR-Lex ; [synthèse ANSSI][anssi-cra].
13. Apple,
    [*Apple Platform Security - Keychain data protection / Secure Enclave*][apple-keychain].
14. GNOME / Arch Wiki, [*GNOME Keyring, Secret Service, libsecret*][arch-gnome-keyring].
15. systemd, [*systemd-creds - encrypted credentials with TPM2*][systemd-creds].

<!-- Définitions des liens (style référence markdown), à maintenir ici uniquement -->

[ms-whitepaper]: https://learn.microsoft.com/en-us/previous-versions/ms995355(v=msdn.10)
[ms-cryptprotect]: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
[ms-cryptunprotect]: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata
[ms-cng-dpapi]: https://learn.microsoft.com/en-us/windows/win32/seccng/cng-dpapi
[ms-protecteddata]: https://learn.microsoft.com/en-us/dotnet/standard/security/how-to-use-data-protection
[picod-bursztein]: https://elie.net/talk/reversing-dpapi-and-stealing-windows-secrets-offline
[synacktiv]: https://www.synacktiv.com/ressources/univershell_2017_dpapi.pdf
[tierzero]: https://tierzerosecurity.co.nz/2024/01/22/data-protection-windows-api.html
[passcape]: https://www.passcape.com/index.php?section=docsys&cmd=details&id=28
[wikipedia-dpapi]: https://en.wikipedia.org/wiki/Data_Protection_API
[ms-win11-24h2]: https://learn.microsoft.com/en-us/windows/whats-new/whats-new-windows-11-version-24h2
[ms-credential-guard]: https://learn.microsoft.com/en-us/windows/security/identity-protection/credential-guard/considerations-known-issues
[ms-hello]: https://learn.microsoft.com/en-us/windows/security/identity-protection/hello-for-business/faq
[eu-cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=fr
[anssi-cra]: https://cyber.gouv.fr/reglementation/cybersecurite-des-produits/cyber-resilience-act/
[apple-keychain]: https://support.apple.com/guide/security/keychain-data-protection-secb0694df1a/web
[arch-gnome-keyring]: https://wiki.archlinux.org/title/GNOME/Keyring
[systemd-creds]: https://www.freedesktop.org/software/systemd/man/latest/systemd-creds.html
