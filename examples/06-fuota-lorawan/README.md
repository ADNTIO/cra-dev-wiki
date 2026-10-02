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

### Prerequisites

Tested on Ubuntu with Zephyr 4.4.2 and Zephyr SDK 1.0.1. Allow about 5 minutes for
the workspace, 2 to 3 minutes per firmware build, 35 minutes for an update over LoRa.

```bash
sudo apt install cmake ninja-build device-tree-compiler git wget xz-utils
sudo usermod -aG dialout $USER   # serial port access; log out and back in
```

Zephyr SDK, minimal archive plus the ESP32 toolchain only:

```bash
cd ~ && B=https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v1.0.1
wget $B/zephyr-sdk-1.0.1_linux-x86_64_minimal.tar.xz \
     $B/toolchain_gnu_linux-x86_64_xtensa-espressif_esp32_zephyr-elf.tar.xz $B/sha256.sum
grep -E "minimal|xtensa-espressif_esp32_zephyr" sha256.sum | sha256sum -c -
tar xf zephyr-sdk-1.0.1_linux-x86_64_minimal.tar.xz
mkdir -p zephyr-sdk-1.0.1/gnu
tar xf toolchain_gnu_linux-x86_64_xtensa-espressif_esp32_zephyr-elf.tar.xz -C zephyr-sdk-1.0.1/gnu
export ZEPHYR_SDK_INSTALL_DIR=~/zephyr-sdk-1.0.1   # no need to run setup.sh
```

### Set up a Zephyr workspace

The workspace lives outside this repository; limited to the modules needed, it takes
under 1 GB. The Python tooling (west, the Zephyr and MCUboot dependencies, esptool,
Pillow) is declared in the `firmware` group of this example's `pyproject.toml`: no
venv to activate, everything goes through `uv run`.

```bash
EX=/path/to/cra-dev-wiki/examples/06-fuota-lorawan
alias zw="uv run --project $EX --group firmware"

mkdir ~/zephyr-fuota && cd ~/zephyr-fuota
zw west init -m https://github.com/zephyrproject-rtos/zephyr --mr v4.4.2 --clone-opt=--depth=1 .
zw west config manifest.project-filter -- '-.*,+mcuboot,+loramac-node,+hal_espressif,+mbedtls,+zcbor,+cmsis_6'
zw west update --narrow -o=--depth=1
```

### Build and flash

The commands below include the overlay for a 26 MHz crystal, which the reference
boards have (`esptool flash-id` shows "Crystal frequency: 26MHz"). With a 40 MHz
crystal, drop the `*_EXTRA_DTC_OVERLAY_FILE` options. Note the syntax: with
`--sysbuild`, options aimed at the application or the bootloader are prefixed with
`firmware_` or `mcuboot_`.

From the workspace:

```bash
APP=$EX/firmware
XTAL="-Dfirmware_EXTRA_DTC_OVERLAY_FILE=$APP/xtal-26mhz.overlay -Dmcuboot_EXTRA_DTC_OVERLAY_FILE=$APP/xtal-26mhz.overlay"

# Once: the signing key, outside any repository, readable by you only
mkdir -p ~/keys && zw imgtool keygen -k ~/keys/fuota.pem -t ecdsa-p256 && chmod 600 ~/keys/fuota.pem

zw west build -b heltec_wifi_lora32_v2/esp32/procpu --sysbuild -s $APP -d build/lorawan -- \
  -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE='"'$HOME'/keys/fuota.pem"' $XTAL \
  -Dfirmware_EXTRA_CONF_FILE=$HOME/keys/lorawan.conf
zw west flash -d build/lorawan --esp-device /dev/ttyUSB0
```

`lorawan.conf` holds your credentials, also outside the repository:

```ini
CONFIG_APP_LORAWAN_DEV_EUI="..."
CONFIG_APP_LORAWAN_JOIN_EUI="..."
CONFIG_APP_LORAWAN_APP_KEY="..."
```

Without `SB_CONFIG_BOOT_SIGNATURE_KEY_FILE`, the build succeeds without a warning and
signs with MCUboot's public example key (`root-ec-p256.pem`). Checked.

To read a board's console (Ctrl-] to quit):

```bash
zw python -m serial.tools.miniterm /dev/ttyUSB0 115200
```

### Testing with a real LoRaWAN network

Not done for this example, which was tested without a gateway. What it takes: a
LoRaWAN gateway, a network server with FUOTA support, the device registered with its
DevEUI, JoinEUI and AppKey, and a FUOTA deployment pushing
`build/lorawan/firmware/zephyr/zephyr.signed.bin` (with a higher version than the
one running) to a class C multicast group.

[ChirpStack v4][chirpstack-fuota] has FUOTA deployments built in; The Things Stack
[documents its FUOTA support][tts-fuota] as early adoption. On the server side, use
the values the firmware is sized for in `prj.conf`: 48-byte fragments, at most 10%
redundancy, an image of at most 384 KB. ChirpStack also asks for a Gen App Key in
LoRaWAN 1.0.x: this firmware passes the same key as AppKey and NwkKey, and
LoRaMac-node derives the multicast root key from it, so set the Gen App Key to the
AppKey (our reading of the source, not tested).


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

First check the radio link in both directions. From the workspace (no sysbuild here,
so the overlay option has no prefix):

```bash
R=$EX/radio-test; X=-DEXTRA_DTC_OVERLAY_FILE=$APP/xtal-26mhz.overlay
zw west build -b heltec_wifi_lora32_v2/esp32/procpu -s $R -d build/ping -- $X
zw west build -b heltec_wifi_lora32_v2/esp32/procpu -s $R -d build/pong -- $X -DEXTRA_CONF_FILE=$R/pong.conf
zw west flash -d build/ping --esp-device /dev/ttyUSB0
zw west flash -d build/pong --esp-device /dev/ttyUSB1
```

Each screen then shows the pings and pongs with the received power; the ping board
shows `out/back dBm` for both directions.

Then the update itself, from the workspace:

```bash
K=-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE='"'$HOME'/keys/fuota.pem"'

# Version 1.0.0 for the board being updated, then a 1.1.0 image to send
zw west build -b heltec_wifi_lora32_v2/esp32/procpu --sysbuild -s $APP -d build/p2p -- \
  $K $XTAL -Dfirmware_EXTRA_CONF_FILE=$APP/p2p.conf
sed -i 's/^VERSION_MINOR = .*/VERSION_MINOR = 1/' $APP/VERSION
zw west build -b heltec_wifi_lora32_v2/esp32/procpu --sysbuild -s $APP -d build/p2p-v2 -- \
  $K $XTAL -Dfirmware_EXTRA_CONF_FILE=$APP/p2p.conf
sed -i 's/^VERSION_MINOR = .*/VERSION_MINOR = 0/' $APP/VERSION

# Sender board
zw west build -b heltec_wifi_lora32_v2/esp32/procpu -s $EX/radio-modem -d build/modem -- $X

zw west flash -d build/p2p --esp-device /dev/ttyUSB0
zw west flash -d build/modem --esp-device /dev/ttyUSB1

# Broadcast (about 35 minutes)
zw python $EX/firmware/tools/p2p_send.py build/p2p-v2/firmware/zephyr/zephyr.signed.bin \
  --modem /dev/ttyUSB1 --device /dev/ttyUSB0
```

The new image must have a higher version than the running one: MCUboot's downgrade
prevention erases anything else.

If the transfer is cut (USB link lost, Ctrl-C), `p2p_send.py` can resume it as long
as the board being updated has not rebooted: pass the session number it printed and
the next fragment, for example `--session 20 --start 151`.

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
  SF10. A second tester measured the same gap with the same pair of boards.
- On these boards, the ESP32 is revision 1: without MCUboot, Zephyr's simple boot
  refuses it, hence `CONFIG_ESP32_USE_UNSUPPORTED_REVISION` in `radio-modem/` and
  `radio-test/`.
- Zephyr's UART console does not take lines longer than 255 characters, and opening
  the serial port resets the modem board: `p2p_send.py` splits the frames and waits
  for `READY`.

### Troubleshooting

- `Could not open port ... the port is busy`: usually a permission problem, not a
  busy port. Check that you are in the `dialout` group (`id`), after logging back in.
- `device not accepting address, error -71` in `dmesg`: a faulty cable or USB port.
- `FileNotFoundError` on `imgtool keygen`: the key folder does not exist yet.


### What was checked, and what was not

Checked on the board: the boot chain above, the presence of the radio (its version
read over SPI), and the screen initialisation (the SSD1306 driver answers on I2C).
The firmware also builds without warnings for `ttgo_lora32/esp32/procpu`, without
having been tried on that board.

Checked over the radio, between two boards: a full update, from the reception of the
TS004 fragments to the confirmed boot of the new image (see above).

A second tester rebuilt everything from these instructions on a fresh machine and got
the same 7 out of 7 on the test bench.

Not checked: everything specific to LoRaWAN. Neither the join, nor clock
synchronisation, nor multicast setup, nor a FUOTA session run by a network server
were exercised; that needs a gateway and a FUOTA server. Triggering the watchdog on
a hang was not provoked either.

[loramac-node]: https://github.com/Lora-net/LoRaMac-node
[fuota-paper]: https://arxiv.org/abs/2002.08735
[chirpstack-fuota]: https://www.chirpstack.io/docs/chirpstack/use/fuota.html
[tts-fuota]: https://www.thethingsindustries.com/docs/concepts/features/lorawan/fuota/
