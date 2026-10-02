"""The core point of the article: the transport says nothing about where the image comes from."""

import random

import pytest

from fuota import image
from fuota.channel import transmit
from fuota.fragmentation import encode, rebuild


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("fuota")
    image.keygen(tmp / "manufacturer.pem", tmp / "manufacturer.pub.pem")
    image.keygen(tmp / "attacker.pem", tmp / "attacker.pub.pem")
    (tmp / "app.bin").write_bytes(random.Random(0).randbytes(10_000))
    image.sign(tmp / "manufacturer.pem", tmp / "app.bin", tmp / "app.signed.bin", "1.1.0")
    return tmp


def over_the_air(data: bytes, seed: int) -> bytes:
    """A full session: fragmentation, 10% loss, rebuild."""
    session, fragments = encode(data, frag_size=48, nb_redundant=60)
    return rebuild(session, transmit(fragments, loss_rate=0.10, seed=seed)).data()


def test_signed_image_is_accepted_after_a_lossy_transfer(workdir):
    received = workdir / "received.bin"
    received.write_bytes(over_the_air((workdir / "app.signed.bin").read_bytes(), seed=1))

    assert image.verify(workdir / "manufacturer.pub.pem", received)


def test_image_from_a_group_key_holder_is_rejected(workdir):
    # The attacker extracted the group key from a device: their fragments are
    # accepted by the transport. They sign with their own key, for lack of better.
    image.sign(workdir / "attacker.pem", workdir / "app.bin", workdir / "rogue.bin", "9.9.9")
    received = workdir / "received-rogue.bin"
    received.write_bytes(over_the_air((workdir / "rogue.bin").read_bytes(), seed=2))

    # The transport worked perfectly, and a plain hash sees nothing wrong.
    assert received.read_bytes() == (workdir / "rogue.bin").read_bytes()
    assert image.hash_is_valid(received)
    # Only the signature makes the difference.
    assert not image.verify(workdir / "manufacturer.pub.pem", received)


def test_modified_image_is_rejected(workdir):
    tampered = bytearray((workdir / "app.signed.bin").read_bytes())
    tampered[2000] ^= 0x01
    received = workdir / "received-tampered.bin"
    received.write_bytes(over_the_air(bytes(tampered), seed=3))

    assert not image.verify(workdir / "manufacturer.pub.pem", received)


def test_truncated_image_is_rejected(workdir):
    signed = (workdir / "app.signed.bin").read_bytes()
    received = workdir / "received-truncated.bin"
    received.write_bytes(signed[: len(signed) // 2])

    assert not image.verify(workdir / "manufacturer.pub.pem", received)
