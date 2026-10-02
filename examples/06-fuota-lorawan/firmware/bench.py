#!/usr/bin/env python3
"""Banc d'essai de la chaîne de démarrage, sur une vraie carte.

Dépose dans le slot secondaire les images qu'une session FUOTA pourrait y laisser
(valide, forgée, altérée, ancienne) et vérifie ce que MCUboot et le firmware en font.
Aucune émission radio : le join est désactivé par bench.conf.

À lancer depuis le dossier de l'exemple, avec uv (groupe « firmware ») :

    uv run --group firmware python firmware/bench.py --workspace ~/zephyr-fuota build [--xtal26]
    uv run --group firmware python firmware/bench.py --workspace ~/zephyr-fuota run --port /dev/ttyUSB0

ATTENTION : `run` efface entièrement la flash de la carte.
"""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parent
WORK = Path("bench-work")  # clés et images de test, dans le workspace
BOARD = "heltec_wifi_lora32_v2/esp32/procpu"

# version -> options de compilation du firmware
FIRMWARES = {
    "1.0.0": ["-Dfirmware_CONFIG_APP_SELFTEST_REQUIRES_JOIN=n"],
    "1.1.0": [],  # test de bon fonctionnement exigeant : sans réseau, il échoue
    "1.2.0": ["-Dfirmware_CONFIG_APP_SELFTEST_REQUIRES_JOIN=n"],
}


def run(*cmd, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True, **kwargs)


def topdir() -> Path:
    return Path(run("west", "topdir").stdout.strip())


def imgtool(*args) -> None:
    run(sys.executable, topdir() / "bootloader/mcuboot/scripts/imgtool.py", *args)


def build_dir(version: str) -> Path:
    return Path("build") / f"bench-{version}"


def set_version(version: str) -> None:
    major, minor, patch = version.split(".")
    (APP / "VERSION").write_text(
        f"VERSION_MAJOR = {major}\nVERSION_MINOR = {minor}\nPATCHLEVEL = {patch}\n"
        "VERSION_TWEAK = 0\nEXTRAVERSION =\n"
    )


def build(args) -> None:
    WORK.mkdir(exist_ok=True)
    for name in ("fabricant", "attaquant"):
        if not (WORK / f"{name}.pem").exists():
            imgtool("keygen", "-k", WORK / f"{name}.pem", "-t", "ecdsa-p256")
    key = (WORK / "fabricant.pem").resolve()

    common = [f'-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE="{key}"', f"-Dfirmware_EXTRA_CONF_FILE={APP / 'bench.conf'}"]
    if args.xtal26:
        overlay = APP / "xtal-26mhz.overlay"
        common += [f"-Dfirmware_EXTRA_DTC_OVERLAY_FILE={overlay}", f"-Dmcuboot_EXTRA_DTC_OVERLAY_FILE={overlay}"]
    try:
        for version, options in FIRMWARES.items():
            print(f"Compilation du firmware {version}...")
            set_version(version)
            run("west", "build", "-p", "always", "-b", args.board, "--sysbuild",
                "-s", APP, "-d", build_dir(version), "--", *common, *options)  # fmt: skip
    finally:
        set_version("1.0.0")

    # Les mêmes options de signature que le build Zephyr, plus --pad : l'image
    # est alors marquée « à l'essai », comme après une réception FUOTA.
    ninja = (build_dir("1.0.0") / "firmware/build.ninja").read_text()
    sign_args = re.search(r"imgtool\.py sign --version \S+ (--header-size \S+ --slot-size \S+ --align \S+)", ninja)
    layout = sign_args.group(1).split()

    def sign(image: str, version: str, key_name: str, firmware: str) -> None:
        imgtool("sign", "--version", version, *layout, "--pad", "--key", WORK / f"{key_name}.pem",
                build_dir(firmware) / "firmware/zephyr/zephyr.bin", WORK / image)  # fmt: skip

    sign("ne-rejoint-pas.bin", "1.1.0", "fabricant", "1.1.0")
    sign("valide.bin", "1.2.0", "fabricant", "1.2.0")
    sign("forgee.bin", "1.3.0", "attaquant", "1.2.0")
    sign("ancienne.bin", "1.0.0", "fabricant", "1.0.0")
    tampered = bytearray((WORK / "valide.bin").read_bytes())
    tampered[0x8000] ^= 0x01
    (WORK / "alteree.bin").write_bytes(tampered)
    print(f"Images de test prêtes dans {WORK}/")


def slot1_offset() -> str:
    dts = (build_dir("1.0.0") / "firmware/zephyr/zephyr.dts").read_text()
    return re.search(r"slot1_partition: partition@(\w+)", dts).group(1)


def console(port: str, seconds: float) -> str:
    """Redémarre la carte par la ligne RTS et rend ce qu'elle écrit."""
    import serial

    link = serial.Serial()
    link.port, link.baudrate, link.timeout = port, 115200, 0.2
    link.dtr = link.rts = False
    link.open()
    link.rts = True
    time.sleep(0.2)
    link.rts = False
    end, raw = time.time() + seconds, b""
    while time.time() < end:
        raw += link.read(4096)
    link.close()
    text = re.sub(r"\x1b\[[0-9;]*m", "", raw.decode("utf-8", "replace"))
    keep = re.compile(r"rst:0x|^I: (Image index|Image version|Starting swap|Image \d)|^[EW]: |fuota:")
    return "\n".join(line.strip() for line in text.splitlines() if keep.search(line))


def esptool(port: str, *args) -> None:
    run(sys.executable, "-m", "esptool", "--port", port, "--baud", "460800", *args)


def bench(args) -> None:
    port, offset = args.port, "0x" + slot1_offset()
    failures = 0

    def step(title: str, image: str | None, seconds: float, expected: list[str], forbidden: list[str] = ()) -> None:
        nonlocal failures
        if image:
            esptool(port, "--after", "no-reset", "write-flash", offset, WORK / image)
        out = console(port, seconds)
        ok = all(e in out for e in expected) and not any(f in out for f in forbidden)
        failures += not ok
        print(f"\n[{'OK' if ok else 'ÉCHEC'}] {title}\n" + "\n".join("    " + line for line in out.splitlines()))

    print("Effacement de la carte, puis MCUboot et firmware 1.0.0...")
    esptool(port, "erase-flash")
    run("west", "flash", "-d", build_dir("1.0.0"), "--esp-device", port)

    step("Démarrage du firmware 1.0.0", None, 8, ["Firmware 1.0.0", "Radio LoRa prête"])
    step("Image forgée, signée par une autre clé : refusée", "forgee.bin", 25,
         ["Image in the secondary slot is not valid", "Firmware 1.0.0"], ["Starting swap"])  # fmt: skip
    step("Image du fabricant altérée d'un bit : refusée", "alteree.bin", 25,
         ["Image in the secondary slot is not valid", "Firmware 1.0.0"], ["Starting swap"])  # fmt: skip
    step("Mise à jour valide qui rate son test : essayée, puis annulée", "ne-rejoint-pas.bin", 40,
         ["Firmware 1.1.0, image à l'essai", "Swap type: revert", "Firmware 1.0.0, image confirmée"])  # fmt: skip
    step("Mise à jour valide qui réussit son test : confirmée", "valide.bin", 20,
         ["Firmware 1.2.0, image à l'essai", "Image confirmée"])  # fmt: skip
    step("Après un reset, la nouvelle image reste en place", None, 8,
         ["Swap type: none", "Firmware 1.2.0, image confirmée"])  # fmt: skip
    step("Ancienne version, pourtant bien signée : refusée", "ancienne.bin", 25,
         ["downgrade prevention", "Firmware 1.2.0"], ["Starting swap"])  # fmt: skip

    print(f"\n{'Tous les essais passent' if not failures else f'{failures} essai(s) en échec'}")
    sys.exit(1 if failures else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", type=Path, required=True, help="workspace Zephyr (créé par west init)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build", help="compile les firmwares et fabrique les images de test")
    p.add_argument("--board", default=BOARD)
    p.add_argument("--xtal26", action="store_true", help="carte à quartz 26 MHz")
    p.set_defaults(func=build)
    p = sub.add_parser("run", help="joue les essais sur la carte (efface sa flash)")
    p.add_argument("--port", required=True)
    p.set_defaults(func=bench)
    args = parser.parse_args()
    # Les chemins relatifs (build/, bench-work/) sont ceux du workspace
    os.chdir(args.workspace.expanduser())
    try:
        args.func(args)
    except subprocess.CalledProcessError as e:
        sys.exit(f"Échec de : {' '.join(e.cmd)}\n{e.stdout[-2000:]}\n{e.stderr[-2000:]}")


if __name__ == "__main__":
    main()
