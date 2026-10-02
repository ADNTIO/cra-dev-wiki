"""Le point central de l'article : le transport ne dit rien de l'origine de l'image."""

import random

import pytest

from fuota import image
from fuota.channel import transmit
from fuota.fragmentation import Decoder, encode


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("fuota")
    image.keygen(tmp / "fabricant.pem", tmp / "fabricant.pub.pem")
    image.keygen(tmp / "attaquant.pem", tmp / "attaquant.pub.pem")
    (tmp / "app.bin").write_bytes(random.Random(0).randbytes(10_000))
    image.sign(tmp / "fabricant.pem", tmp / "app.bin", tmp / "app.signed.bin", "1.1.0")
    return tmp


def over_the_air(data: bytes, seed: int) -> bytes:
    """Une session complète : fragmentation, 10 % de pertes, reconstruction."""
    session, fragments = encode(data, frag_size=48, nb_redundant=60)
    decoder = Decoder(session)
    for index, fragment in transmit(fragments, loss_rate=0.10, seed=seed):
        if decoder.push(index, fragment):
            break
    return decoder.data()


def test_signed_image_is_accepted_after_a_lossy_transfer(workdir):
    received = workdir / "recu.bin"
    received.write_bytes(over_the_air((workdir / "app.signed.bin").read_bytes(), seed=1))

    assert image.verify(workdir / "fabricant.pub.pem", received)


def test_image_from_a_group_key_holder_is_rejected(workdir):
    # L'attaquant a extrait la clé du groupe d'un appareil : ses fragments sont
    # acceptés par le transport. Il signe avec sa propre clé, faute de mieux.
    image.sign(workdir / "attaquant.pem", workdir / "app.bin", workdir / "pirate.bin", "9.9.9")
    received = workdir / "recu-pirate.bin"
    received.write_bytes(over_the_air((workdir / "pirate.bin").read_bytes(), seed=2))

    # Le transport a parfaitement fonctionné, et un simple hash n'y voit rien.
    assert received.read_bytes() == (workdir / "pirate.bin").read_bytes()
    assert image.hash_is_valid(received)
    # Seule la signature fait la différence.
    assert not image.verify(workdir / "fabricant.pub.pem", received)


def test_modified_image_is_rejected(workdir):
    tampered = bytearray((workdir / "app.signed.bin").read_bytes())
    tampered[2000] ^= 0x01
    received = workdir / "recu-modifie.bin"
    received.write_bytes(over_the_air(bytes(tampered), seed=3))

    assert not image.verify(workdir / "fabricant.pub.pem", received)


def test_truncated_image_is_rejected(workdir):
    signed = (workdir / "app.signed.bin").read_bytes()
    received = workdir / "recu-tronque.bin"
    received.write_bytes(signed[: len(signed) // 2])

    assert not image.verify(workdir / "fabricant.pub.pem", received)
