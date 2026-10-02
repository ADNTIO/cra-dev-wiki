"""Diffuse une image signée par LoRa point à point, via la carte « modem ».

    uv run --group firmware python firmware/tools/p2p_send.py IMAGE \\
        --modem /dev/ttyUSB1 [--device /dev/ttyUSB0] [--limit N]

Le PC fragmente l'image (codage TS004, fuota/fragmentation.py) et confie chaque
trame à la carte modem (radio-modem/), qui l'émet. Entre deux trames, le PC attend
neuf fois la durée d'émission : 10 % de temps d'émission au plus, la limite de la
sous-bande 869,4 - 869,65 MHz. Le protocole est décrit dans firmware/src/p2p.h.

Avec --device, la console de la carte à mettre à jour est suivie en parallèle et
recopiée, préfixée par « [appareil] », jusqu'à ce qu'elle redémarre sur la
nouvelle image.
"""

import argparse
import math
import random
import struct
import sys
import threading
import time
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fuota.fragmentation import encode  # noqa: E402

SETUP, READY, FRAG, DONE = 1, 2, 3, 4
FRAG_SIZE = 200  # CONFIG_LORAWAN_FRAG_TRANSPORT_MAX_FRAG_SIZE de p2p.conf
MAX_REDUNDANCY = 0.10  # CONFIG_LORAWAN_FRAG_TRANSPORT_MAX_REDUNDANCY
DUTY_CYCLE = 0.10


class Modem:
    def __init__(self, port: str):
        self.link = serial.Serial(port, 115200, timeout=0.05)
        self.received: list[tuple[bytes, int, int]] = []
        self._buffer = b""

    def _lines(self, timeout: float):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self._buffer += self.link.read(4096)
            while b"\n" in self._buffer:
                raw, self._buffer = self._buffer.split(b"\n", 1)
                line = raw.decode("ascii", "replace").strip()
                if line.startswith("RX "):
                    _, hexdata, rssi, snr = line.split()
                    self.received.append((bytes.fromhex(hexdata), int(rssi), int(snr)))
                    continue
                yield line

    def write_line(self, line: str) -> None:
        # La console du modem renvoie l'écho de chaque caractère, au même débit :
        # envoyée d'un bloc, une longue ligne fait déborder sa FIFO de réception.
        data = line.encode() + b"\n"
        for i in range(0, len(data), 32):
            self.link.write(data[i : i + 32])
            self.link.flush()
            time.sleep(0.004)

    def command(self, line: str, timeout: float = 5) -> str:
        self.write_line(line)
        for reply in self._lines(timeout):
            if reply.startswith(("OK", "ERR")):
                return reply
        raise TimeoutError(f"pas de réponse du modem à {line[:20]!r}")

    def hello(self) -> None:
        self.link.reset_input_buffer()
        # Ouvrir le port redémarre la carte : on attend son « READY »
        for _ in range(5):
            self.write_line("HELLO")
            if any(line == "READY" for line in self._lines(2)):
                self._lines_flush()
                return
        raise TimeoutError("le modem ne répond pas (radio-modem flashé ?)")

    def _lines_flush(self) -> None:
        for _ in self._lines(0.5):
            pass

    def send(self, frame: bytes) -> float:
        """Émet une trame ; rend la durée d'émission, en secondes."""
        # Une ligne de console du modem ne dépasse pas 255 caractères
        chunks = [frame[i : i + 100] for i in range(0, len(frame), 100)]
        for chunk in chunks[:-1]:
            reply = self.command("DATA " + chunk.hex())
            if reply != "OK":
                raise RuntimeError(reply)
        reply = self.command("TX " + chunks[-1].hex())
        if not reply.startswith("OK"):
            raise RuntimeError(reply)
        return int(reply.split()[1]) / 1000

    def listen(self, seconds: float) -> None:
        for _ in self._lines(seconds):
            pass

    def take(self, kind: int, session: int):
        """Retire et rend la première trame reçue du type voulu, ou None."""
        for i, (frame, rssi, snr) in enumerate(self.received):
            if frame[:2] == b"AD" and len(frame) >= 4 and frame[2] == kind and frame[3] == session:
                del self.received[i]
                return frame[4:], rssi, snr
        return None


def follow_device(port: str, stop: threading.Event) -> None:
    link = serial.Serial(port, 115200, timeout=0.2)
    buffer = b""
    while not stop.is_set():
        buffer += link.read(4096)
        while b"\n" in buffer:
            raw, buffer = buffer.split(b"\n", 1)
            line = raw.decode("utf-8", "replace").strip()
            line = "".join(c for c in line if c.isprintable())
            if any(k in line for k in ("p2p:", "fuota:", "I: Image", "I: Starting swap", "E: ", "Swap type")):
                print(f"[appareil] {line}", flush=True)
    link.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="image signée (zephyr.signed.bin)")
    parser.add_argument("--modem", required=True, help="port série de la carte modem")
    parser.add_argument("--device", help="port série de la carte à mettre à jour, pour suivre sa console")
    parser.add_argument("--redundancy", type=float, default=0.08, help="part de fragments redondants")
    parser.add_argument("--limit", type=int, help="n'envoyer que N fragments (essai de liaison)")
    parser.add_argument("--wait-reboot", type=float, default=60, help="secondes à suivre l'appareil après DONE")
    args = parser.parse_args()

    if args.redundancy > MAX_REDUNDANCY:
        sys.exit(f"redondance > {MAX_REDUNDANCY:.0%} : le décodeur de l'appareil la refuserait")

    data = args.image.read_bytes()
    m = math.ceil(len(data) / FRAG_SIZE)
    session_info, fragments = encode(data, FRAG_SIZE, math.ceil(m * args.redundancy))
    if args.limit:
        fragments = fragments[: args.limit]
    session = random.randint(1, 255)
    print(f"Image {args.image.name} : {len(data)} octets, {session_info.nb_frag} fragments "
          f"+ {len(fragments) - min(len(fragments), session_info.nb_frag)} redondants, session {session}")

    stop = threading.Event()
    if args.device:
        threading.Thread(target=follow_device, args=(args.device, stop), daemon=True).start()

    modem = Modem(args.modem)
    modem.hello()
    modem.command("SHOW Session %u" % session)

    # 1. Annonce de la session ; l'appareil efface son slot secondaire, puis répond
    setup = b"AD" + bytes([SETUP, session]) + struct.pack("<HBB", session_info.nb_frag, FRAG_SIZE,
                                                          session_info.padding)
    for attempt in range(1, 6):
        airtime = modem.send(setup)
        modem.listen(max(15, airtime / DUTY_CYCLE))
        reply = modem.take(READY, session)
        if reply:
            payload, rssi, snr = reply
            if payload[0] != 0:
                sys.exit(f"L'appareil refuse la session (statut {payload[0]})")
            print(f"Appareil prêt (RSSI {rssi} dBm, SNR {snr} dB)")
            break
        print(f"Pas de réponse à l'annonce, essai {attempt}/5")
    else:
        stop.set()
        sys.exit("L'appareil ne répond pas")

    # 2. Les fragments, au rythme permis par le temps d'émission
    start = time.monotonic()
    done = None
    for index, fragment in enumerate(fragments, start=1):
        airtime = modem.send(b"AD" + bytes([FRAG, session]) + struct.pack("<H", index) + fragment)
        modem.listen(airtime * (1 / DUTY_CYCLE - 1))
        done = modem.take(DONE, session)
        if index % 50 == 0 or index == len(fragments):
            elapsed = time.monotonic() - start
            eta = elapsed / index * (len(fragments) - index)
            print(f"Fragment {index}/{len(fragments)}, {elapsed / 60:.1f} min, reste ~{eta / 60:.1f} min",
                  flush=True)
            modem.command(f"SHOW Frag {index}")
        if done:
            break

    if not done:
        modem.listen(10)
        done = modem.take(DONE, session)
    elapsed = time.monotonic() - start
    if not done:
        print(f"Aucun DONE après {index} fragments ({elapsed / 60:.1f} min)")
        stop.set()
        sys.exit(1)

    payload, rssi, snr = done
    lost, recovered = struct.unpack("<HH", payload[:4])
    print(f"DONE reçu après {index} fragments en {elapsed / 60:.1f} min : "
          f"{recovered} fragment(s) perdu(s) puis reconstruit(s)")
    modem.command("SHOW Envoi OK")

    if args.device:
        time.sleep(args.wait_reboot)
    stop.set()


if __name__ == "__main__":
    main()
