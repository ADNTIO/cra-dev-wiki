# Example: firmware update over LoRaWAN (FUOTA)

Companion code for episode 6 of the "CRA & Dev" series,
[A thousand fragments, one signature](../../docs/en/CRA-Dev-06-FUOTA-LoRaWAN.md).

Two parts:

- [the simulation](#the-simulation), in Python, without hardware;
- [the firmware](#the-firmware), for Zephyr and MCUboot, on an ESP32 board with a LoRa
  radio.

## The simulation

It replays on your machine what a real session does:

1. the manufacturer signs an image in the MCUboot format, with `imgtool`;
2. the server splits it into fragments and adds redundancy (LoRaWAN TS004);
3. the radio link loses frames;
4. the device rebuilds the image and checks its signature, as MCUboot does at boot;
5. an attacker who holds the group key broadcasts their own image: the transport
   accepts it, the hash is fine, the signature rejects it.

### Run

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv run python -m fuota.demo   # the session, step by step
uv run pytest                 # the tests
```

Demo output (the image and the keys are random, so the signed size varies by a byte
from one run to the next):

```
1. Manufacturer: sign the image
   signed image: 20664 bytes
2. Server: fragment, with redundancy
   431 fragments + 87 redundant
3. Radio: 10% of frames lost
   image rebuilt: True
4. Device: check the signature before booting
   valid signature: True
5. Attacker: holds the group key and broadcasts their own image
   image rebuilt: True
   valid hash:      True
   valid signature: False
6. Radio budget for this image (EU868, 1% duty cycle)
   DR0 (SF12):  40.2 h
   DR2 (SF10):  10.0 h
   DR5 (SF7):   1.2 h
```

### What is inside

| File | Role |
| --- | --- |
| `fuota/fragmentation.py` | Fragment coding and decoding, as in TS004 v1.0.0 |
| `fuota/image.py` | Signing and verification, with the `imgtool` commands from the article |
| `fuota/channel.py` | A radio link that loses frames |
| `fuota/airtime.py` | Airtime of a frame and duration of a session |
| `fuota/demo.py` | The end-to-end session |
| `tests/` | What the example guarantees |

### What was checked, and what was not

The fragment coding was checked against Semtech's reference decoder
(`FragDecoder.c`, in [LoRaMac-node][loramac-node]): the parity matrix lines are
identical, and sessions encoded here, with losses, are rebuilt identically by that C
decoder. Two reference lines are pinned in `tests/test_fragmentation.py`.

The airtime calculation gives the same values as `SX1276GetLoRaTimeOnAirNumerator()`
from the same repository, for SF7 to SF12 and every frame size.

The radio budget is more pessimistic than the [study][fuota-paper] cited in the
article: about 21 hours instead of 17 for 50 kB at DR2. The study counts 51 bytes of
firmware per frame; here we remove the fragment header (3 bytes) and count the real
LoRaWAN header (13 bytes). The order of magnitude is the same.

What the simulation does not do: it talks to no radio, does not encrypt the
fragments, implements neither clock synchronisation (TS003) nor multicast setup
(TS005), and its decoder is not the low-memory one of a real device.

## The firmware

The `firmware/` folder holds the full Zephyr application from the article: OTAA
join, the three FUOTA services, and the rule "a received image boots on trial and is
only confirmed once it has proven itself". On the Heltec board, the OLED screen shows
the ADNT logo at boot, then each step. MCUboot is set up to require an ECDSA P-256
signature, check the image at every boot, be able to go back to the previous image,
and reject an older version.

| File | Role |
| --- | --- |
| `src/main.c` | The application |
| `src/screen.c`, `src/logo.h` | The screen: logo, then the steps |
| `boards/heltec_wifi_lora32_v2_esp32_procpu.overlay` | Declares the Heltec OLED screen |
| `tools/make_logo.py`, `assets/` | Generates `src/logo.h` from the ADNT logo |
| `prj.conf` | LoRaWAN stack, FUOTA services, fragment decoder sizing |
| `sysbuild.conf`, `sysbuild/mcuboot.conf` | Bootloader settings |
| `Kconfig` | LoRaWAN credentials and health check |
| `bench.conf`, `bench.py` | Test bench on a board |
| `xtal-26mhz.overlay` | For boards with a 26 MHz crystal |

### Set up a Zephyr workspace

Tested with Zephyr 4.4.2 and Zephyr SDK 1.0.1 (`xtensa-espressif_esp32_zephyr-elf`
toolchain). The workspace lives outside this repository; limited to the modules
needed, it takes about 1.8 GB, SDK included.

The Python tooling (west, the Zephyr and MCUboot dependencies, esptool, Pillow) is
declared in the `firmware` group of this example's `pyproject.toml`: no venv to
activate, everything goes through `uv run`.

```bash
EX=/path/to/cra-dev-wiki/examples/06-fuota-lorawan
export ZEPHYR_SDK_INSTALL_DIR=/path/to/zephyr-sdk-1.0.1

mkdir ~/zephyr-fuota && cd ~/zephyr-fuota
uv run --project $EX --group firmware west init \
  -m https://github.com/zephyrproject-rtos/zephyr --mr v4.4.2 --clone-opt=--depth=1 .
uv run --project $EX --group firmware west config manifest.project-filter -- \
  '-.*,+mcuboot,+loramac-node,+hal_espressif,+mbedtls,+zcbor,+cmsis_6'
uv run --project $EX --group firmware west update --narrow -o=--depth=1
```

### Build and flash

From the workspace:

```bash
APP=$EX/firmware
alias zw="uv run --project $EX --group firmware"

# Once: the signing key, outside any repository
zw imgtool keygen -k ~/keys/fuota.pem -t ecdsa-p256

zw west build -b heltec_wifi_lora32_v2/esp32/procpu --sysbuild -s $APP -- \
  -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE='"'$HOME'/keys/fuota.pem"' \
  -Dfirmware_EXTRA_CONF_FILE=$HOME/keys/lorawan.conf
zw west flash --esp-device /dev/ttyUSB0
```

`lorawan.conf` holds your credentials, also outside the repository:

```ini
CONFIG_APP_LORAWAN_DEV_EUI="..."
CONFIG_APP_LORAWAN_JOIN_EUI="..."
CONFIG_APP_LORAWAN_APP_KEY="..."
```

The image to hand to the FUOTA server is `build/firmware/zephyr/zephyr.signed.bin`.
The server must send 48-byte fragments, with at most 10% redundancy, for an image of
at most 384 KB: these are the values set in `prj.conf`, and they decide how much RAM
the decoder reserves.

If `esptool flash-id` shows "Crystal frequency: 26MHz", add
`-Dfirmware_EXTRA_DTC_OVERLAY_FILE=$APP/xtal-26mhz.overlay` and
`-Dmcuboot_EXTRA_DTC_OVERLAY_FILE=$APP/xtal-26mhz.overlay`.

Without `SB_CONFIG_BOOT_SIGNATURE_KEY_FILE`, the build succeeds without a warning and
signs with MCUboot's public example key (`root-ec-p256.pem`). Checked.

### The screen

At boot, the ADNT logo stays on for three seconds. Then come the steps, four lines at
a time, the most recent at the bottom:

| Screen | Step |
| --- | --- |
| `v1.2.0 trial` / `v1.2.0 ok` | Version, and image state: on trial or confirmed |
| `Radio OK` | The SX1276 radio answers |
| `Join 1/3`, `Join OK`, `Join failed` | OTAA join (`Join off` on the bench) |
| `Confirmed` | The test image passed its health check |
| `FUOTA ready` | FUOTA services started |
| `Uplink OK` | Periodic uplink, which opens the receive windows |
| `DL 200 mcast`, `DL 201 frag`, `DL 202 clock`, `DL 2 app` | Downlink received, by port |
| `Image rcvd`, `Rebooting` | Image complete: MCUboot will verify it |

Zephyr's framebuffer font only covers ASCII. On a board without a screen declared in
the devicetree, the display is simply skipped.

`src/logo.h` is generated from `assets/adnt-mark-black.png`:

```bash
uv run --group firmware python firmware/tools/make_logo.py --preview preview.png
```

The ADNT logo is a trademark of ADNT Sàrl; it is not covered by the wiki's CC BY-SA
licence. Replace it with your own for your own product.

### The test bench

`bench.py` drops into the secondary slot the images a FUOTA session could leave
there, resets the board and checks the console. It transmits nothing over the radio.
It erases the whole flash of the board.

From the example folder:

```bash
uv run --group firmware python firmware/bench.py --workspace ~/zephyr-fuota build --xtal26
uv run --group firmware python firmware/bench.py --workspace ~/zephyr-fuota run --port /dev/ttyUSB0
```

Without `--xtal26` for a board with a 40 MHz crystal.

Result on a Heltec board with an ESP32 and an SX1276 (ESP32-D0WDQ6 rev 1.0, 4 MB of
flash, 26 MHz crystal), built with Zephyr's `heltec_wifi_lora32_v2` definition:

| Check | What the console says |
| --- | --- |
| Firmware 1.0.0 boots | `Firmware 1.0.0, image confirmed`, `LoRa radio ready` |
| Forged image, signed with another key | `E: Image in the secondary slot is not valid!` |
| Manufacturer image with one flipped bit | `E: Image in the secondary slot is not valid!` |
| Valid update that fails its health check | `Firmware 1.1.0, image on trial`, then `Swap type: revert` and back to 1.0.0 |
| Valid update that passes its health check | `Firmware 1.2.0, image on trial`, `Image confirmed` |
| Reset after confirmation | `Swap type: none`, `Firmware 1.2.0, image confirmed` |
| Old version 1.0.0, correctly signed | `I: Image 0 in slot 1 erased due to downgrade prevention` |

### Update over LoRa between two boards

Without a LoRaWAN gateway or server, a second board can act as the sender. The
transport is then point-to-point LoRa, not LoRaWAN: no network server, no encryption,
no multicast, no clock synchronisation. Everything else is that of a FUOTA session:
TS004 fragment coding, Zephyr's TS004 decoder and secondary-slot writes, then MCUboot
checking the signature and booting the image on trial.

| Item | Role |
| --- | --- |
| `firmware/p2p.conf`, `firmware/src/p2p.c` | Board being updated: listens for sessions, rebuilds the image |
| `radio-modem/` | Sender board: LoRa modem driven by the PC over the serial console |
| `firmware/tools/p2p_send.py` | PC: fragments the image (`fuota/fragmentation.py`) and broadcasts it |
| `radio-test/` | Ping-pong radio test, to check the link in both directions |

The protocol is described at the top of `firmware/src/p2p.h`. The downlink, which
carries the fragments, uses SF7 at 250 kHz; the uplink, which only carries the
acknowledgements, uses SF10 at 125 kHz. Both are at 869.525 MHz, 14 dBm, and the PC
keeps to the 10% duty cycle of that sub-band.

```bash
# Board being updated (MCUboot + point-to-point firmware)
zw west build -b heltec_wifi_lora32_v2/esp32/procpu --sysbuild -s $APP -d build/p2p -- \
  -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE='"'$HOME'/keys/fuota.pem"' \
  -Dfirmware_EXTRA_CONF_FILE=$APP/p2p.conf
zw west flash -d build/p2p --esp-device /dev/ttyUSB0

# Sender board
zw west build -b heltec_wifi_lora32_v2/esp32/procpu -s $EX/radio-modem -d build/modem
zw west flash -d build/modem --esp-device /dev/ttyUSB1

# Broadcast a new signed image (from the example folder)
uv run --group firmware python firmware/tools/p2p_send.py build/p2p-v2/firmware/zephyr/zephyr.signed.bin \
  --modem /dev/ttyUSB1 --device /dev/ttyUSB0
```

Add the `xtal-26mhz.overlay` overlay to both boards if their crystal runs at 26 MHz.

Result on two Heltec boards side by side, from version 1.0.0 to 1.1.0:

```
Image zephyr.signed.bin: 200439 bytes, 1003 fragments + 81 redundant, session 20
Device ready (RSSI -129 dBm, SNR -4 dB)
[device] p2p: Image complete: 1004 fragments received, 7 lost, 7 rebuilt
DONE received after 1011 fragments in 33.4 min: 7 fragment(s) lost then rebuilt
[device] fuota: Rebooting: new image received, MCUboot will verify it
[device] I: Image index: 0, Swap type: test
[device] I: Starting swap using scratch algorithm.
[device] I: Image version: v1.1.0
[device] fuota: Firmware 1.1.0, image on trial
[device] fuota: Image confirmed
```

After a reset, the board boots straight into 1.1.0 (`Swap type: none`).

The console excerpts in this section and the previous one were captured before the
firmware messages were translated into English; they are shown with today's wording.

Three things learned along the way:

- The link was very asymmetric: at 14 dBm, one board heard the other at −82 dBm,
  but was heard at −126 dBm, at the edge of reception in SF7. Hence the uplink in
  SF10. Check both directions with `radio-test/` first.
- On these boards, the ESP32 is revision 1: without MCUboot, Zephyr's simple boot
  refuses it, hence `CONFIG_ESP32_USE_UNSUPPORTED_REVISION` in `radio-modem/` and
  `radio-test/`.
- Zephyr's UART console does not take lines longer than 255 characters, and opening
  the serial port resets the modem board: `p2p_send.py` splits the frames and waits
  for `READY`.

### What was checked, and what was not

Checked on the board: the boot chain above, the presence of the radio (its version
read over SPI), and the screen initialisation (the SSD1306 driver answers on I2C).
The firmware also builds without warnings for `ttgo_lora32/esp32/procpu`, without
having been tried on that board.

Checked over the radio, between two boards: a full update, from the reception of the
TS004 fragments to the confirmed boot of the new image (see above).

Not checked: everything specific to LoRaWAN. Neither the join, nor clock
synchronisation, nor multicast setup, nor a FUOTA session run by a network server
were exercised; that needs a gateway and a FUOTA server. Triggering the watchdog on
a hang was not provoked either.

[loramac-node]: https://github.com/Lora-net/LoRaMac-node
[fuota-paper]: https://arxiv.org/abs/2002.08735
