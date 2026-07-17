# DPAPI, in-depth article

> English translation pending. This long-form, fully sourced article is currently
> available in French. The short episode
> [CRA & Dev #3: DPAPI](../CRA-Dev-03-DPAPI.md) is already available in English.
>
> Read the full French version:
> [DPAPI, article de fond](../../fr/ressources/DPAPI-Article-de-fond.md).

## What this article covers

The in-depth article goes well beyond the short episode. It covers:

- History: DPAPI from Windows 2000 to Windows 11, based on primary sources (the 2001
  NAI Labs and Microsoft whitepaper, Microsoft Learn, academic research).
- Internals: the MasterKey, the session key, PBKDF2 derivation, secondary entropy,
  MasterKey expiration, the CREDHIST credential history, and the domain backup key
  mechanism.
- Machine-level protection: the `CRYPTPROTECT_LOCAL_MACHINE` flag, machine
  MasterKeys under `S-1-5-18`, and the `DPAPI_SYSTEM` LSA secret.
- Algorithm evolution: from 3DES and SHA-1 to AES-256-CBC and HMAC-SHA-512 across
  Windows versions.
- DPAPI-NG (CNG DPAPI): multi-machine and multi-principal secret sharing, present
  since Windows 8, not Windows 11.
- Windows 10 versus Windows 11: what actually differs (not the DPAPI core, but the
  surrounding hardening such as LSA protection, SHA-3, and PDE).
- Security and threat model: offline attacks, memory extraction, the domain backup
  key as a high-value target.
- Beyond DPAPI: TPM-backed CNG keys, Windows Hello for Business, Credential Guard and
  VBS, Personal Data Encryption, passkeys and FIDO2.
- Similarities with macOS and Linux: Keychain and Secure Enclave, Secret Service,
  GNOME Keyring, KWallet, and `systemd-creds`.
- Evolution timeline and future outlook, plus a full bibliography.

A full English translation will be added here. Until then, the French version is the
authoritative reference.
