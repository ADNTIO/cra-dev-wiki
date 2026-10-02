"""Fragmentation with redundancy, as in LoRaWAN TS004 v1.0.0.

The image is split into M fixed-size fragments. The server sends these M fragments
as they are, then redundant fragments: each one is the XOR of a pseudo-random subset
of the original fragments. The device rebuilds the image as soon as it has received
enough fragments, whichever they are.

Reference: annex of the specification (matrix_line and prbs23 functions).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    """What the server announces to the device before transmitting (FragSessionSetupReq)."""

    nb_frag: int  # M: number of fragments without redundancy
    frag_size: int  # size of a fragment, in bytes
    padding: int  # padding bytes added to the last fragment


def _prbs23(x: int) -> int:
    b0 = x & 1
    b1 = (x >> 5) & 1
    return (x >> 1) + ((b0 ^ b1) << 22)


def matrix_line(n: int, m: int) -> int:
    """Line n (from 1) of the parity matrix, for M = m fragments.

    The result is a mask: bit i set means that fragment i (from 0) is part of the
    XOR of the n-th redundant fragment.
    """
    # Powers of 2 are handled separately, they produce patterns.
    pow2 = 1 if m & (m - 1) == 0 else 0
    x = 1 + 1001 * n
    line = 0
    for _ in range(m // 2):
        r = 1 << 16
        while r >= m:
            x = _prbs23(x)
            r = x % (m + pow2)
        line |= 1 << r
    return line


def encode(data: bytes, frag_size: int, nb_redundant: int) -> tuple[Session, list[bytes]]:
    """Splits data and adds nb_redundant redundancy fragments.

    fragments[i] has index i + 1: TS004 counts from 1.
    """
    if frag_size <= 0 or not data:
        raise ValueError("empty image or invalid fragment size")
    padding = -len(data) % frag_size
    padded = data + bytes(padding)
    m = len(padded) // frag_size
    session = Session(nb_frag=m, frag_size=frag_size, padding=padding)

    uncoded = [padded[i * frag_size : (i + 1) * frag_size] for i in range(m)]
    values = [int.from_bytes(f, "big") for f in uncoded]

    coded = []
    for n in range(1, nb_redundant + 1):
        line = matrix_line(n, m)
        acc = 0
        for i in range(m):
            if line >> i & 1:
                acc ^= values[i]
        coded.append(acc.to_bytes(frag_size, "big"))
    return session, uncoded + coded


class Decoder:
    """Rebuilds the image from the received fragments, in any order.

    Each fragment is an equation over GF(2): a mask (which original fragments it
    combines) and a value. We keep an echelon system; once it holds M independent
    equations, the image is known.

    Teaching version: a real device uses a low-memory algorithm, but the result is
    the same.
    """

    def __init__(self, session: Session):
        self.session = session
        self._rows: dict[int, tuple[int, int]] = {}  # pivot -> (mask, value)

    @property
    def complete(self) -> bool:
        return len(self._rows) == self.session.nb_frag

    def push(self, index: int, fragment: bytes) -> bool:
        """Adds the fragment with the given index (from 1). Returns complete."""
        m = self.session.nb_frag
        # Never trust lengths announced by the network: this is exactly the check
        # that was missing in CVE-2026-13480.
        if index < 1:
            raise ValueError("invalid fragment index")
        if len(fragment) != self.session.frag_size:
            raise ValueError("unexpected fragment size")

        mask = 1 << (index - 1) if index <= m else matrix_line(index - m, m)
        value = int.from_bytes(fragment, "big")
        while mask:
            pivot = (mask & -mask).bit_length() - 1
            if pivot not in self._rows:
                self._rows[pivot] = (mask, value)
                break
            row_mask, row_value = self._rows[pivot]
            mask ^= row_mask
            value ^= row_value
        return self.complete

    def data(self) -> bytes:
        """The rebuilt image, without the padding."""
        if not self.complete:
            raise ValueError("not enough fragments to rebuild the image")
        m, size = self.session.nb_frag, self.session.frag_size
        solved = [0] * m
        for pivot in range(m - 1, -1, -1):
            mask, value = self._rows[pivot]
            rest = mask ^ (1 << pivot)
            while rest:
                solved[pivot] ^= solved[(rest & -rest).bit_length() - 1]
                rest &= rest - 1
            solved[pivot] ^= value
        image = b"".join(v.to_bytes(size, "big") for v in solved)
        return image[: len(image) - self.session.padding]


def rebuild(session: Session, frames) -> Decoder:
    """Feeds (index, fragment) pairs to a new decoder until the image is complete."""
    decoder = Decoder(session)
    for index, fragment in frames:
        if decoder.push(index, fragment):
            break
    return decoder
