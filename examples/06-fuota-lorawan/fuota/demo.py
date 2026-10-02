"""An end-to-end FUOTA session, without a radio: python -m fuota.demo"""

import math
import os
import tempfile
from pathlib import Path

from fuota import airtime, image
from fuota.channel import transmit
from fuota.fragmentation import Decoder, encode

FIRMWARE_SIZE = 20_000
FRAG_SIZE = 48  # 51 bytes at DR0-DR2, minus the fragment header
REDUNDANCY = 0.20
LOSS_RATE = 0.10


def receive(session, frames) -> Decoder:
    decoder = Decoder(session)
    for index, fragment in frames:
        if decoder.push(index, fragment):
            break
    return decoder


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        print("1. Manufacturer: sign the image")
        image.keygen(tmp / "manufacturer.pem", tmp / "manufacturer.pub.pem")
        (tmp / "app.bin").write_bytes(os.urandom(FIRMWARE_SIZE))
        image.sign(tmp / "manufacturer.pem", tmp / "app.bin", tmp / "app.signed.bin", "1.1.0")
        signed = (tmp / "app.signed.bin").read_bytes()
        print(f"   signed image: {len(signed)} bytes")

        print("2. Server: fragment, with redundancy")
        m = math.ceil(len(signed) / FRAG_SIZE)
        session, fragments = encode(signed, FRAG_SIZE, math.ceil(m * REDUNDANCY))
        print(f"   {session.nb_frag} fragments + {len(fragments) - session.nb_frag} redundant")

        print(f"3. Radio: {LOSS_RATE:.0%} of frames lost")
        decoder = receive(session, transmit(fragments, LOSS_RATE, seed=1))
        print(f"   image rebuilt: {decoder.complete}")
        (tmp / "received.bin").write_bytes(decoder.data())

        print("4. Device: check the signature before booting")
        print(f"   valid signature: {image.verify(tmp / 'manufacturer.pub.pem', tmp / 'received.bin')}")

        print("5. Attacker: holds the group key and broadcasts their own image")
        image.keygen(tmp / "attacker.pem", tmp / "attacker.pub.pem")
        image.sign(tmp / "attacker.pem", tmp / "app.bin", tmp / "rogue.bin", "9.9.9")
        rogue = (tmp / "rogue.bin").read_bytes()
        session, fragments = encode(rogue, FRAG_SIZE, math.ceil(m * REDUNDANCY))
        decoder = receive(session, transmit(fragments, LOSS_RATE, seed=2))
        (tmp / "received-rogue.bin").write_bytes(decoder.data())
        print(f"   image rebuilt: {decoder.complete}")
        print(f"   valid hash:      {image.hash_is_valid(tmp / 'received-rogue.bin')}")
        print(f"   valid signature: {image.verify(tmp / 'manufacturer.pub.pem', tmp / 'received-rogue.bin')}")

    print("6. Radio budget for this image (EU868, 1% duty cycle)")
    for dr in (airtime.EU868[0], airtime.EU868[2], airtime.EU868[5]):
        hours = airtime.session_duration(len(signed), dr, REDUNDANCY) / 3600
        print(f"   {dr.name} (SF{dr.sf}): {hours:5.1f} h")


if __name__ == "__main__":
    main()
