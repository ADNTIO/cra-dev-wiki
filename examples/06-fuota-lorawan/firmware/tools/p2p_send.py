"""Broadcasts a signed image over point-to-point LoRa, through the "modem" board.

    uv run --group firmware python firmware/tools/p2p_send.py IMAGE \\
        --modem /dev/ttyUSB1 [--device /dev/ttyUSB0] [--limit N]

The PC fragments the image (TS004 coding, fuota/fragmentation.py) and hands each
frame to the modem board (radio-modem/), which transmits it. Between two frames,
the PC waits nine times the airtime: a 10% duty cycle at most, the limit of the
869.4 - 869.65 MHz sub-band. The protocol is described in firmware/src/p2p.h.

With --device, the console of the board being updated is followed in parallel and
copied, prefixed with "[device]", until it reboots on the new image.

If the transfer is cut (serial link lost, Ctrl-C), resume it with the session
number it printed and the next fragment index, for example
`--session 20 --start 151`. This only works if the device has not rebooted in the
meantime: it keeps its session as long as it is powered.
"""

import argparse
import math
import random
import re
import struct
import sys
import threading
import time
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fuota.fragmentation import encode  # noqa: E402

SETUP, READY, FRAG, DONE = 1, 2, 3, 4
FRAG_SIZE = 200  # CONFIG_LORAWAN_FRAG_TRANSPORT_MAX_FRAG_SIZE from p2p.conf
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
                    # The modem prints RX lines from its radio callback: one may
                    # interleave with another output. Skip it rather than abort.
                    try:
                        _, hexdata, rssi, snr = line.split()
                        self.received.append((bytes.fromhex(hexdata), int(rssi), int(snr)))
                    except ValueError:
                        pass
                    continue
                yield line

    def write_line(self, line: str) -> None:
        # The modem console echoes every character at the same rate: sent in one
        # go, a long line overflows its receive FIFO.
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
        raise TimeoutError(f"no answer from the modem to {line[:20]!r}")

    def hello(self) -> None:
        self.link.reset_input_buffer()
        # Opening the port resets the board: wait for its "READY"
        for _ in range(5):
            self.write_line("HELLO")
            if any(line == "READY" for line in self._lines(2)):
                self._lines_flush()
                return
        raise TimeoutError("the modem does not answer (is radio-modem flashed?)")

    def _lines_flush(self) -> None:
        for _ in self._lines(0.5):
            pass

    def send(self, frame: bytes) -> float:
        """Transmits a frame; returns the airtime, in seconds."""
        # A modem console line is at most 255 characters long
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
        """Removes and returns the first received frame of the given type, or None."""
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
            line = re.sub(r"\x1b\[[0-9;]*m", "", raw.decode("utf-8", "replace")).strip()
            line = "".join(c for c in line if c.isprintable())
            if any(k in line for k in ("p2p:", "fuota:", "I: Image", "I: Starting swap", "E: ", "Swap type")):
                print(f"[device] {line}", flush=True)
    link.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="signed image (zephyr.signed.bin)")
    parser.add_argument("--modem", required=True, help="serial port of the modem board")
    parser.add_argument("--device", help="serial port of the board being updated, to follow its console")
    parser.add_argument("--redundancy", type=float, default=0.08, help="share of redundant fragments")
    parser.add_argument("--limit", type=int, help="only send N fragments (link test)")
    parser.add_argument("--wait-reboot", type=float, default=60, help="seconds to follow the device after DONE")
    parser.add_argument("--session", type=int, help="resume this session instead of starting a new one")
    parser.add_argument("--start", type=int, default=1, help="first fragment index to send (to resume)")
    args = parser.parse_args()

    if args.redundancy > MAX_REDUNDANCY:
        sys.exit(f"redundancy > {MAX_REDUNDANCY:.0%}: the device decoder would reject it")

    data = args.image.read_bytes()
    m = math.ceil(len(data) / FRAG_SIZE)
    session_info, fragments = encode(data, FRAG_SIZE, math.ceil(m * args.redundancy))
    if args.limit:
        fragments = fragments[: args.limit]
    session = args.session or random.randint(1, 255)
    print(f"Image {args.image.name}: {len(data)} bytes, {session_info.nb_frag} fragments "
          f"+ {len(fragments) - min(len(fragments), session_info.nb_frag)} redundant, session {session}")

    stop = threading.Event()
    if args.device:
        threading.Thread(target=follow_device, args=(args.device, stop), daemon=True).start()

    modem = Modem(args.modem)
    modem.hello()
    modem.command("SHOW Session %u" % session)

    # 1. Session announcement; the device erases its secondary slot, then answers
    setup = b"AD" + bytes([SETUP, session]) + struct.pack("<HBB", session_info.nb_frag, FRAG_SIZE,
                                                          session_info.padding)
    for attempt in range(1, 6):
        airtime = modem.send(setup)
        modem.listen(max(15, airtime / DUTY_CYCLE))
        reply = modem.take(READY, session)
        if reply:
            payload, rssi, snr = reply
            if payload[0] != 0:
                sys.exit(f"The device rejects the session (status {payload[0]})")
            print(f"Device ready (RSSI {rssi} dBm, SNR {snr} dB)")
            break
        print(f"No answer to the announcement, attempt {attempt}/5")
    else:
        stop.set()
        sys.exit("The device does not answer")

    # 2. The fragments, at the pace the duty cycle allows
    start = time.monotonic()
    done = None
    index = args.start - 1
    for index, fragment in enumerate(fragments[args.start - 1 :], start=args.start):
        airtime = modem.send(b"AD" + bytes([FRAG, session]) + struct.pack("<H", index) + fragment)
        modem.listen(airtime * (1 / DUTY_CYCLE - 1))
        done = modem.take(DONE, session)
        if index % 50 == 0 or index == len(fragments):
            elapsed = time.monotonic() - start
            eta = elapsed / (index - args.start + 1) * (len(fragments) - index)
            print(f"Fragment {index}/{len(fragments)}, {elapsed / 60:.1f} min, ~{eta / 60:.1f} min left",
                  flush=True)
            modem.command(f"SHOW Frag {index}")
        if done:
            break

    if not done:
        modem.listen(10)
        done = modem.take(DONE, session)
    elapsed = time.monotonic() - start
    if not done:
        print(f"No DONE after {index} fragments ({elapsed / 60:.1f} min)")
        stop.set()
        sys.exit(1)

    payload, rssi, snr = done
    lost, recovered = struct.unpack("<HH", payload[:4])
    print(f"DONE received after {index} fragments in {elapsed / 60:.1f} min: "
          f"{recovered} fragment(s) lost then rebuilt")
    modem.command("SHOW Sent OK")

    if args.device:
        time.sleep(args.wait_reboot)
    stop.set()


if __name__ == "__main__":
    main()
