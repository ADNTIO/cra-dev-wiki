"""Une session FUOTA de bout en bout, sans radio : python -m fuota.demo"""

import math
import os
import tempfile
from pathlib import Path

from fuota import airtime, image
from fuota.channel import transmit
from fuota.fragmentation import Decoder, encode

FIRMWARE_SIZE = 20_000
FRAG_SIZE = 48  # 51 octets à DR0-DR2, moins l'en-tête de fragment
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

        print("1. Fabricant : signer l'image")
        image.keygen(tmp / "fabricant.pem", tmp / "fabricant.pub.pem")
        (tmp / "app.bin").write_bytes(os.urandom(FIRMWARE_SIZE))
        image.sign(tmp / "fabricant.pem", tmp / "app.bin", tmp / "app.signed.bin", "1.1.0")
        signed = (tmp / "app.signed.bin").read_bytes()
        print(f"   image signée : {len(signed)} octets")

        print("2. Serveur : fragmenter, avec redondance")
        m = math.ceil(len(signed) / FRAG_SIZE)
        session, fragments = encode(signed, FRAG_SIZE, math.ceil(m * REDUNDANCY))
        print(f"   {session.nb_frag} fragments + {len(fragments) - session.nb_frag} redondants")

        print(f"3. Radio : {LOSS_RATE:.0%} de trames perdues")
        decoder = receive(session, transmit(fragments, LOSS_RATE, seed=1))
        print(f"   image reconstruite : {decoder.complete}")
        (tmp / "recu.bin").write_bytes(decoder.data())

        print("4. Appareil : vérifier la signature avant de démarrer")
        print(f"   signature valide : {image.verify(tmp / 'fabricant.pub.pem', tmp / 'recu.bin')}")

        print("5. Attaquant : il détient la clé du groupe et diffuse sa propre image")
        image.keygen(tmp / "attaquant.pem", tmp / "attaquant.pub.pem")
        image.sign(tmp / "attaquant.pem", tmp / "app.bin", tmp / "pirate.bin", "9.9.9")
        pirate = (tmp / "pirate.bin").read_bytes()
        session, fragments = encode(pirate, FRAG_SIZE, math.ceil(m * REDUNDANCY))
        decoder = receive(session, transmit(fragments, LOSS_RATE, seed=2))
        (tmp / "recu-pirate.bin").write_bytes(decoder.data())
        print(f"   image reconstruite : {decoder.complete}")
        print(f"   hash valide        : {image.hash_is_valid(tmp / 'recu-pirate.bin')}")
        print(f"   signature valide   : {image.verify(tmp / 'fabricant.pub.pem', tmp / 'recu-pirate.bin')}")

    print("6. Budget radio pour cette image (EU868, 1 % de temps d'émission)")
    for dr in (airtime.EU868[0], airtime.EU868[2], airtime.EU868[5]):
        hours = airtime.session_duration(len(signed), dr, REDUNDANCY) / 3600
        print(f"   {dr.name} (SF{dr.sf}) : {hours:5.1f} h")


if __name__ == "__main__":
    main()
