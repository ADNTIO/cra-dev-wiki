import random

import pytest

from fuota.channel import transmit
from fuota.fragmentation import Decoder, encode, matrix_line


def bits(line: int, m: int) -> str:
    return "".join("1" if line >> i & 1 else "0" for i in range(m))


def receive(session, frames) -> Decoder:
    decoder = Decoder(session)
    for index, fragment in frames:
        if decoder.push(index, fragment):
            break
    return decoder


def test_matrix_line_matches_the_reference_decoder():
    # Values produced by FragGetParityMatrixRow() from the LoRaMac-node reference
    # decoder (FragDecoder.c), including the special case M = power of 2.
    assert bits(matrix_line(1, 26), 26) == "11010011100011001100010110"
    assert bits(matrix_line(3, 32), 32) == "00000110001011000101010000110000"


def test_first_fragments_are_the_image_itself():
    data = bytes(range(200))
    session, fragments = encode(data, frag_size=20, nb_redundant=5)
    assert session.nb_frag == 10
    assert b"".join(fragments[:10]) == data


def test_redundant_fragment_is_a_xor_of_original_fragments():
    data = random.Random(0).randbytes(26 * 8)
    session, fragments = encode(data, frag_size=8, nb_redundant=1)
    line = matrix_line(1, session.nb_frag)
    expected = bytes(8)
    for i in range(session.nb_frag):
        if line >> i & 1:
            expected = bytes(a ^ b for a, b in zip(expected, fragments[i]))
    assert fragments[session.nb_frag] == expected


def test_padding_is_removed():
    data = b"firmware" * 13  # 104 bytes: not a multiple of 48
    session, fragments = encode(data, frag_size=48, nb_redundant=0)
    assert session.padding == 40
    assert receive(session, enumerate(fragments, start=1)).data() == data


def test_image_survives_ten_percent_loss_with_twenty_percent_redundancy():
    data = random.Random(1).randbytes(20_000)
    session, fragments = encode(data, frag_size=48, nb_redundant=84)
    received = list(transmit(fragments, loss_rate=0.10, seed=1))
    assert len(received) < len(fragments)  # frames were indeed lost

    decoder = receive(session, received)

    assert decoder.complete
    assert decoder.data() == data


def test_too_much_loss_leaves_the_image_incomplete():
    data = random.Random(2).randbytes(20_000)
    session, fragments = encode(data, frag_size=48, nb_redundant=20)  # ~5 %

    decoder = receive(session, transmit(fragments, loss_rate=0.30, seed=2))

    assert not decoder.complete
    with pytest.raises(ValueError):
        decoder.data()


def test_fragment_order_does_not_matter():
    data = random.Random(3).randbytes(5_000)
    session, fragments = encode(data, frag_size=50, nb_redundant=30)
    received = list(transmit(fragments, loss_rate=0.10, seed=3))
    random.Random(3).shuffle(received)

    assert receive(session, received).data() == data


def test_decoder_rejects_a_fragment_of_the_wrong_size():
    session, fragments = encode(bytes(100), frag_size=10, nb_redundant=2)
    decoder = Decoder(session)
    with pytest.raises(ValueError):
        decoder.push(1, fragments[0] + b"\x00")
    with pytest.raises(ValueError):
        decoder.push(0, fragments[0])
