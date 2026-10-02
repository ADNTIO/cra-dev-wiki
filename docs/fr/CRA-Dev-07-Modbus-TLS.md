---
description: >-
  Modbus/TCP accepte n'importe quelle commande venue du réseau. Modbus/TCP Security (TLS mutuel, port 802, rôles dans le certificat), ou à défaut un service désactivé par défaut et cloisonné : la protection contre l'accès non autorisé exigée par le CRA (Annexe I, partie I, 2 d).
---

# Modbus ne demande jamais « qui est là ? » : TLS mutuel et rôles

> **CRA & Dev #7** · [Série « CRA & Dev »](index.md) · Lecture : environ 6 min · Industriel, Modbus ·
> Exemple : Python (pymodbus)

## Ce que demande le CRA

Le [Cyber Resilience Act][cra] demande qu'un produit se protège contre l'accès non
autorisé, par authentification ou gestion des identités et des accès, et qu'il
signale les accès non autorisés possibles (Annexe I, partie I, point 2, d). S'y
ajoutent une configuration sécurisée par défaut (point b) et une surface d'attaque
limitée, interfaces externes comprises (point j).

Pour un automate, un variateur ou un contrôleur d'axes, la question est donc : quand
une commande Modbus arrive, le produit sait-il qui l'envoie ?

## Le piège classique

Modbus/TCP n'a ni mot de passe ni notion d'utilisateur : tout client qui atteint le
port 502 lit et écrit ce que l'appareil expose. Ce n'est pas un bogue, c'est le
protocole, et les passerelles Modbus série vers Ethernet en héritent.

Le logiciel malveillant FrostyGoop, analysé par [Dragos][dragos], s'en sert : en
Modbus TCP sur le port 502, il a privé de chauffage les clients d'un réseau de
chaleur ukrainien pendant deux jours. Les avis de sécurité suivent le même motif,
comme la [CVE-2025-48466][cve-advantech], où un attaquant non authentifié pilote les
sorties d'un module d'E/S. Et « notre réseau est isolé » ne tient pas : un poste de
maintenance ou un routeur d'accès distant compromis atteint le port 502 de
l'intérieur.

## La technique : Modbus/TCP Security

Modbus.org a spécifié [Modbus/TCP Security][mbsec] (« mbaps »), sur le port 802
[enregistré à l'IANA][iana]. Les trames Modbus ne changent pas, elles passent dans
une session TLS 1.2 ou plus récente (R-01). Le client présente lui aussi un
certificat X.509, sans quoi l'appareil coupe la session (R-02, R-10). Le certificat
porte un rôle, dans l'extension `1.3.6.1.4.1.50316.802.1` (R-21), et chaque requête
est autorisée ou non selon ce rôle ; un refus renvoie l'exception Modbus 01, *Illegal
function* (R-31).

![Un client sans certificat, ou avec un certificat d'une autre autorité, est coupé à la poignée de main TLS ; un client reconnu est autorisé ou non requête par requête, selon le rôle inscrit dans son certificat.](images/modbus-tls.svg)

Côté appareil, en Python avec [pymodbus][pymodbus] (extrait simplifié de
`mbsec/plc.py`) :

```python
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version = ssl.TLSVersion.TLSv1_2   # R-01
ctx.verify_mode = ssl.CERT_REQUIRED            # R-02 : certificat client obligatoire
ctx.load_verify_locations("ca.crt")            # signé par l'autorité de l'installation

def callback_connected(self):                  # une fois par session
    der = self.transport.get_extra_info("ssl_object").getpeercert(binary_form=True)
    self.role = role_from_certificate(der)

async def handle_request(self):                # à chaque requête
    if not self.server.rules.authorise(self.role, self.last_pdu.function_code):
        log.warning("DENIED ...")              # signaler (CRA, point d)
        return self.reply_exception(ExcCodes.ILLEGAL_FUNCTION)   # R-31
    await super().handle_request()
```

Les règles, par exemple « `Operator` lit, `Engineer` lit et écrit », vivent dans un
fichier `rules.toml` que l'exploitant peut modifier, comme l'exige la spécification
(R-27).

La [démonstration][example] fait tourner deux automates simulés qui pilotent la
broche d'une machine-outil. Le premier cas rejoue le geste de FrostyGoop : un client
quelconque réécrit la consigne. Extrait de `uv run python -m mbsec.demo` :

```
1. Legacy PLC, plain Modbus/TCP: anyone on the network sets the spindle to 60000 rpm
   write: accepted
3. Client with an Engineer role, signed by its own CA
   write: rejected, the PLC closed the TLS session
4. Operator (HMI): may read, may not write
   read:  12000 rpm
   write: refused, Modbus exception 1 (Illegal function)
6. Engineer (maintenance laptop): may write
   write: accepted
```

Le cas 3 compte : n'importe qui peut fabriquer un certificat `Engineer`. Seule la
signature de l'autorité de l'installation lui donne de la valeur.

## Quand l'appareil ne peut pas faire de TLS

Le CRA n'impose pas de protocole. Sans Modbus/TCP Security, livrez au moins le
service Modbus/TCP désactivé par défaut (point b), limité au nécessaire (lecture
seule, interface dédiée, liste blanche d'adresses, point j), et documentez qu'il doit
rester dans une zone réseau cloisonnée. Une liste blanche d'adresses IP réduit
l'exposition mais n'authentifie personne : sur le même réseau, une adresse se
falsifie.

## Trois choses à savoir

1. Le vrai travail, c'est l'infrastructure de clés : une autorité par installation,
   des certificats qui expirent et qu'on peut retirer, la clé de l'autorité hors
   ligne ou dans un HSM, comme la clé de signature de
   l'[épisode 6](CRA-Dev-06-FUOTA-LoRaWAN.md).
2. La spécification prévoit une suite sans chiffrement, `TLS_RSA_WITH_NULL_SHA256`
   (R-67) : authentifiée, mais en clair. L'activer, c'est renoncer à la
   confidentialité (point e).
3. TLS ne protège pas d'un client légitime compromis : un poste de maintenance piraté
   garde son rôle `Engineer`. Des rôles étroits limitent les dégâts, et le journal des
   refus aide à repérer un client qui sort de son rôle. Les sessions TLS refusées,
   elles, n'atteignent jamais Modbus : journalisez-les dans la couche TLS.

## À retenir

Modbus/TCP exécute ce qu'on lui envoie sans demander qui l'envoie. Modbus/TCP
Security pose la question : un certificat signé par l'installation pour entrer, un
rôle pour décider de chaque requête, un refus journalisé. À défaut, le service doit
être éteint par défaut, restreint et cloisonné.

---

*Épisode précédent : [Mille fragments, une seule signature, mettre à jour un
firmware par LoRaWAN](CRA-Dev-06-FUOTA-LoRaWAN.md).*

*Épisode suivant : [Un journal qui ne peut pas mentir, chaîner et signer ses
logs](CRA-Dev-08-Signed-Logs.md).*

*Code d'accompagnement, dans [`examples/07-modbus-tls`][example] : les deux automates
simulés, la démonstration et ses tests.*

[cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=fr
[mbsec]: https://www.modbus.org/file/secure/modbussecurityprotocol.pdf
[iana]: https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml?search=mbap-s
[dragos]: https://www.dragos.com/blog/protect-against-frostygoop-ics-malware-targeting-operational-technology/
[cve-advantech]: https://www.cve.org/CVERecord?id=CVE-2025-48466
[pymodbus]: https://pymodbus.readthedocs.io/
[example]: https://github.com/ADNTIO/cra-dev-wiki/tree/main/examples/07-modbus-tls
