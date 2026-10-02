# Exemple : mise à jour de firmware par LoRaWAN (FUOTA)

Code d'accompagnement de l'épisode 6 de la série « CRA & Dev »,
[Mille fragments, une seule signature](../../docs/fr/CRA-Dev-06-FUOTA-LoRaWAN.md).

*English: companion code for episode 6, in two parts. A Python simulation of a full
LoRaWAN FUOTA session (sign, fragment, lose frames, rebuild, verify), showing that
only the signature stops an attacker who holds the multicast group key. And a
complete Zephyr firmware for ESP32 LoRa boards, with a test bench that checks the
MCUboot boot chain on real hardware. Comments are in French; the commands below are
all you need.*

Deux parties :

- [la simulation](#la-simulation), en Python, sans matériel ;
- [le firmware](#le-firmware), pour Zephyr et MCUboot, sur une carte ESP32 avec radio
  LoRa.

## La simulation

Elle rejoue sur votre machine ce que fait une vraie session :

1. le fabricant signe une image au format MCUboot, avec `imgtool` ;
2. le serveur la découpe en fragments et ajoute de la redondance (LoRaWAN TS004) ;
3. le lien radio perd des trames ;
4. l'appareil reconstruit l'image et vérifie sa signature, comme MCUboot au démarrage ;
5. un attaquant qui détient la clé du groupe diffuse sa propre image : le transport
   l'accepte, le hash est bon, la signature la rejette.

### Lancer

Ce projet utilise [uv](https://docs.astral.sh/uv/).

```bash
uv run python -m fuota.demo   # la session, étape par étape
uv run pytest                 # les tests
```

Sortie de la démonstration (l'image et les clés sont tirées au hasard, la taille
signée varie d'un octet d'une exécution à l'autre) :

```
1. Fabricant : signer l'image
   image signée : 20663 octets
2. Serveur : fragmenter, avec redondance
   431 fragments + 87 redondants
3. Radio : 10% de trames perdues
   image reconstruite : True
4. Appareil : vérifier la signature avant de démarrer
   signature valide : True
5. Attaquant : il détient la clé du groupe et diffuse sa propre image
   image reconstruite : True
   hash valide        : True
   signature valide   : False
6. Budget radio pour cette image (EU868, 1 % de temps d'émission)
   DR0 (SF12) :  40.2 h
   DR2 (SF10) :  10.0 h
   DR5 (SF7) :   1.2 h
```

### Ce qu'il y a dedans

| Fichier | Rôle |
| --- | --- |
| `fuota/fragmentation.py` | Codage et décodage des fragments selon TS004 v1.0.0 |
| `fuota/image.py` | Signature et vérification, par les commandes `imgtool` de l'article |
| `fuota/channel.py` | Un lien radio qui perd des trames |
| `fuota/airtime.py` | Temps d'émission d'une trame et durée d'une session |
| `fuota/demo.py` | La session de bout en bout |
| `tests/` | Ce que l'exemple garantit |

### Ce qui a été vérifié, et ce qui ne l'est pas

Le codage des fragments a été confronté au décodeur de référence de Semtech
(`FragDecoder.c`, dans [LoRaMac-node][loramac-node]) : les lignes de la matrice de
parité sont identiques, et des sessions encodées ici, avec pertes, sont
reconstruites à l'identique par ce décodeur C. Deux lignes de référence sont figées
dans `tests/test_fragmentation.py`.

Le calcul du temps d'émission donne les mêmes valeurs que
`SX1276GetLoRaTimeOnAirNumerator()` du même dépôt, pour SF7 à SF12 et toutes les
tailles de trame.

Le budget radio est plus pessimiste que l'[étude][fuota-paper] citée dans l'article :
environ 21 heures au lieu de 17 pour 50 ko à DR2. L'étude compte 51 octets de
firmware par trame ; ici on retire l'en-tête de fragment (3 octets) et on compte
l'en-tête LoRaWAN réel (13 octets). L'ordre de grandeur est le même.

Ce que la simulation ne fait pas : elle ne parle à aucune radio, ne chiffre pas les
fragments, n'implémente ni la synchronisation d'horloge (TS003) ni la configuration
du multicast (TS005), et son décodeur n'est pas celui, économe en mémoire, d'un vrai
appareil.

## Le firmware

Le dossier `firmware/` contient l'application Zephyr complète de l'article : join
OTAA, les trois services FUOTA, et la règle « une image reçue démarre à l'essai et
n'est confirmée qu'après avoir fait ses preuves ». Sur la carte Heltec, l'écran OLED
affiche le logo ADNT au démarrage, puis chaque étape. MCUboot y est réglé pour exiger
une signature ECDSA P-256, vérifier l'image à chaque démarrage, pouvoir revenir à
l'image précédente et refuser une version plus ancienne.

| Fichier | Rôle |
| --- | --- |
| `src/main.c` | L'application |
| `src/screen.c`, `src/logo.h` | L'écran : logo, puis les étapes |
| `boards/heltec_wifi_lora32_v2_esp32_procpu.overlay` | Déclaration de l'écran OLED de la Heltec |
| `tools/make_logo.py`, `assets/` | Génération de `src/logo.h` depuis le logo ADNT |
| `prj.conf` | Pile LoRaWAN, services FUOTA, dimensionnement du décodeur de fragments |
| `sysbuild.conf`, `sysbuild/mcuboot.conf` | Réglages du bootloader |
| `Kconfig` | Identifiants LoRaWAN et critère de bon fonctionnement |
| `bench.conf`, `bench.py` | Banc d'essai sur carte |
| `xtal-26mhz.overlay` | Pour les cartes à quartz 26 MHz |

### Préparer un workspace Zephyr

Testé avec Zephyr 4.4.2 et le SDK Zephyr 1.0.1 (chaîne
`xtensa-espressif_esp32_zephyr-elf`). Le workspace se crée hors de ce dépôt ; limité
aux modules utiles, il pèse environ 1,8 Go, SDK compris.

L'outillage Python (west, les dépendances de Zephyr et de MCUboot, esptool, Pillow)
est déclaré dans le groupe `firmware` du `pyproject.toml` de cet exemple : pas de
venv à activer, tout passe par `uv run`.

```bash
EX=/chemin/vers/cra-dev-wiki/examples/06-fuota-lorawan
export ZEPHYR_SDK_INSTALL_DIR=/chemin/vers/zephyr-sdk-1.0.1

mkdir ~/zephyr-fuota && cd ~/zephyr-fuota
uv run --project $EX --group firmware west init \
  -m https://github.com/zephyrproject-rtos/zephyr --mr v4.4.2 --clone-opt=--depth=1 .
uv run --project $EX --group firmware west config manifest.project-filter -- \
  '-.*,+mcuboot,+loramac-node,+hal_espressif,+mbedtls,+zcbor,+cmsis_6'
uv run --project $EX --group firmware west update --narrow -o=--depth=1
```

### Compiler et flasher

Depuis le workspace :

```bash
APP=$EX/firmware
alias zw="uv run --project $EX --group firmware"

# Une fois : la clé de signature, hors de tout dépôt
zw imgtool keygen -k ~/cles/fuota.pem -t ecdsa-p256

zw west build -b heltec_wifi_lora32_v2/esp32/procpu --sysbuild -s $APP -- \
  -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE='"'$HOME'/cles/fuota.pem"' \
  -Dfirmware_EXTRA_CONF_FILE=$HOME/cles/lorawan.conf
zw west flash --esp-device /dev/ttyUSB0
```

`lorawan.conf` porte vos identifiants, hors dépôt eux aussi :

```ini
CONFIG_APP_LORAWAN_DEV_EUI="..."
CONFIG_APP_LORAWAN_JOIN_EUI="..."
CONFIG_APP_LORAWAN_APP_KEY="..."
```

L'image à confier au serveur FUOTA est `build/firmware/zephyr/zephyr.signed.bin`. Le
serveur doit envoyer des fragments de 48 octets, avec au plus 10 % de redondance,
pour une image d'au plus 384 Ko : ce sont les valeurs fixées dans `prj.conf`, et
elles déterminent la RAM réservée par le décodeur.

Si `esptool flash-id` affiche « Crystal frequency: 26MHz », ajoutez
`-Dfirmware_EXTRA_DTC_OVERLAY_FILE=$APP/xtal-26mhz.overlay` et
`-Dmcuboot_EXTRA_DTC_OVERLAY_FILE=$APP/xtal-26mhz.overlay`.

Sans `SB_CONFIG_BOOT_SIGNATURE_KEY_FILE`, le build réussit sans avertissement et
signe avec la clé d'exemple publique de MCUboot (`root-ec-p256.pem`). Vérifié.

### L'écran

Au démarrage, le logo ADNT reste affiché trois secondes. Viennent ensuite les
étapes, quatre lignes à la fois, la plus récente en bas :

| Écran | Étape |
| --- | --- |
| `v1.2.0 essai` / `v1.2.0 ok` | Version, et état de l'image : à l'essai ou confirmée |
| `Radio OK` | La radio SX1276 répond |
| `Join 1/3`, `Join OK`, `Join echec` | Join OTAA (`Join desact.` sur le banc) |
| `Confirmee` | L'image à l'essai a réussi son test |
| `FUOTA pret` | Services FUOTA lancés |
| `Uplink OK` | Uplink périodique, qui ouvre les fenêtres de réception |
| `DL 200 mcast`, `DL 201 frag`, `DL 202 heure`, `DL 2 appli` | Downlink reçu, par port |
| `Image recue`, `Redemarrage` | Image complète : MCUboot va la vérifier |

La police du framebuffer de Zephyr ne couvre que l'ASCII, d'où l'absence d'accents.
Sur une carte sans écran déclaré dans le devicetree, l'affichage est simplement
ignoré.

`src/logo.h` est généré depuis `assets/adnt-mark-black.png` :

```bash
uv run --group firmware python firmware/tools/make_logo.py --preview apercu.png
```

Le logo ADNT est une marque d'ADNT Sàrl ; il n'est pas couvert par la licence
CC BY-SA du wiki. Remplacez-le par le vôtre pour votre propre produit.

### Le banc d'essai

`bench.py` dépose dans le slot secondaire les images qu'une session FUOTA pourrait y
laisser, redémarre la carte et vérifie la console. Il n'émet rien en radio. Il efface
entièrement la flash de la carte.

Depuis le dossier de l'exemple :

```bash
uv run --group firmware python firmware/bench.py --workspace ~/zephyr-fuota build --xtal26
uv run --group firmware python firmware/bench.py --workspace ~/zephyr-fuota run --port /dev/ttyUSB0
```

Sans `--xtal26` pour une carte à quartz 40 MHz.

Résultat sur une carte Heltec à ESP32 et SX1276 (ESP32-D0WDQ6 rev 1.0, 4 Mo de flash,
quartz 26 MHz), compilée avec la définition `heltec_wifi_lora32_v2` de Zephyr :

| Essai | Ce que dit la console |
| --- | --- |
| Démarrage du firmware 1.0.0 | `Firmware 1.0.0, image confirmée`, `Radio LoRa prête` |
| Image forgée, signée par une autre clé | `E: Image in the secondary slot is not valid!` |
| Image du fabricant altérée d'un bit | `E: Image in the secondary slot is not valid!` |
| Mise à jour valide qui rate son test | `Firmware 1.1.0, image à l'essai`, puis `Swap type: revert` et retour à 1.0.0 |
| Mise à jour valide qui réussit son test | `Firmware 1.2.0, image à l'essai`, `Image confirmée` |
| Reset après confirmation | `Swap type: none`, `Firmware 1.2.0, image confirmée` |
| Ancienne version 1.0.0, bien signée | `I: Image 0 in slot 1 erased due to downgrade prevention` |

### Mise à jour par LoRa entre deux cartes

Sans passerelle ni serveur LoRaWAN, une deuxième carte peut jouer l'émetteur. Le
transport est alors du LoRa point à point, pas du LoRaWAN : ni serveur réseau, ni
chiffrement, ni multicast, ni synchronisation d'horloge. Tout le reste est celui
d'une session FUOTA : codage TS004 des fragments, décodeur TS004 et écriture dans le
slot secondaire de Zephyr, puis MCUboot qui vérifie la signature et démarre l'image
à l'essai.

| Élément | Rôle |
| --- | --- |
| `firmware/p2p.conf`, `firmware/src/p2p.c` | Carte à mettre à jour : écoute les sessions, reconstruit l'image |
| `radio-modem/` | Carte émettrice : modem LoRa piloté par le PC sur la console série |
| `firmware/tools/p2p_send.py` | PC : fragmente l'image (`fuota/fragmentation.py`) et la diffuse |
| `radio-test/` | Test radio ping-pong, pour vérifier la liaison dans les deux sens |

Le protocole est décrit en tête de `firmware/src/p2p.h`. Le sens descendant, qui
porte les fragments, est en SF7 à 250 kHz ; le sens montant, qui ne porte que les
accusés, est en SF10 à 125 kHz. Les deux sont à 869,525 MHz, 14 dBm, et le PC
respecte les 10 % de temps d'émission de cette sous-bande.

```bash
# Carte à mettre à jour (MCUboot + firmware point à point)
zw west build -b heltec_wifi_lora32_v2/esp32/procpu --sysbuild -s $APP -d build/p2p -- \
  -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE='"'$HOME'/cles/fuota.pem"' \
  -Dfirmware_EXTRA_CONF_FILE=$APP/p2p.conf
zw west flash -d build/p2p --esp-device /dev/ttyUSB0

# Carte émettrice
zw west build -b heltec_wifi_lora32_v2/esp32/procpu -s $EX/radio-modem -d build/modem
zw west flash -d build/modem --esp-device /dev/ttyUSB1

# Diffusion d'une nouvelle image signée (depuis le dossier de l'exemple)
uv run --group firmware python firmware/tools/p2p_send.py build/p2p-v2/firmware/zephyr/zephyr.signed.bin \
  --modem /dev/ttyUSB1 --device /dev/ttyUSB0
```

Ajoutez l'overlay `xtal-26mhz.overlay` aux deux cartes si leur quartz est à 26 MHz.

Résultat sur deux cartes Heltec côte à côte, de la version 1.0.0 à la 1.1.0 :

```
Image zephyr.signed.bin : 200439 octets, 1003 fragments + 81 redondants, session 20
Appareil prêt (RSSI -129 dBm, SNR -4 dB)
[appareil] p2p: Image complète : 1004 fragments reçus, 7 perdus, 7 reconstruits
DONE reçu après 1011 fragments en 33.4 min : 7 fragment(s) perdu(s) puis reconstruit(s)
[appareil] fuota: Redémarrage : nouvelle image reçue, MCUboot va la vérifier
[appareil] I: Image index: 0, Swap type: test
[appareil] I: Starting swap using scratch algorithm.
[appareil] I: Image version: v1.1.0
[appareil] fuota: Firmware 1.1.0, image à l'essai
[appareil] fuota: Image confirmée
```

Après un reset, la carte démarre directement en 1.1.0 (`Swap type: none`).

Trois choses apprises en route :

- La liaison était très asymétrique : à 14 dBm, une carte entendait l'autre à
  −82 dBm, mais était entendue à −126 dBm, à la limite de réception en SF7. D'où le
  sens montant en SF10. Vérifiez vos deux sens avec `radio-test/` avant tout.
- Sur ces cartes, l'ESP32 est en révision 1 : sans MCUboot, le démarrage simple
  de Zephyr le refuse, d'où `CONFIG_ESP32_USE_UNSUPPORTED_REVISION` dans
  `radio-modem/` et `radio-test/`.
- La console UART de Zephyr ne prend pas de ligne de plus de 255 caractères, et
  ouvrir le port série redémarre la carte modem : `p2p_send.py` découpe les trames
  et attend le `READY`.

### Ce qui a été vérifié, et ce qui ne l'est pas

Vérifié sur la carte : la chaîne de démarrage ci-dessus, la présence de la radio
(lecture de sa version par SPI), et l'initialisation de l'écran (le pilote SSD1306
répond sur l'I2C). Le firmware compile aussi sans avertissement pour
`ttgo_lora32/esp32/procpu`, sans avoir été essayé sur cette carte.

Vérifié par radio, entre deux cartes : une mise à jour complète, de la réception
des fragments TS004 au démarrage confirmé de la nouvelle image (voir ci-dessus).

Pas vérifié : tout ce qui est propre à LoRaWAN. Ni le join, ni la synchronisation
d'horloge, ni la configuration du multicast, ni une session FUOTA par un serveur
réseau n'ont été exercés ; il faut pour cela une passerelle et un serveur FUOTA. Le
déclenchement du chien de garde sur blocage n'a pas été provoqué non plus.

[loramac-node]: https://github.com/Lora-net/LoRaMac-node
[fuota-paper]: https://arxiv.org/abs/2002.08735
