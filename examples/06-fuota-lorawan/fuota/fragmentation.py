"""Fragmentation avec redondance, selon LoRaWAN TS004 v1.0.0.

L'image est découpée en M fragments de taille fixe. Le serveur envoie ces M
fragments tels quels, puis des fragments redondants : chacun est le XOR d'un
sous-ensemble pseudo-aléatoire des fragments d'origine. L'appareil reconstruit
l'image dès qu'il a reçu assez de fragments, quels qu'ils soient.

Référence : annexe de la spécification (fonctions matrix_line et prbs23).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    """Ce que le serveur annonce à l'appareil avant d'émettre (FragSessionSetupReq)."""

    nb_frag: int  # M : nombre de fragments sans redondance
    frag_size: int  # taille d'un fragment, en octets
    padding: int  # octets de bourrage ajoutés au dernier fragment


def _prbs23(x: int) -> int:
    b0 = x & 1
    b1 = (x >> 5) & 1
    return (x >> 1) + ((b0 ^ b1) << 22)


def matrix_line(n: int, m: int) -> int:
    """Ligne n (à partir de 1) de la matrice de parité, pour M = m fragments.

    Le résultat est un masque : le bit i à 1 signifie que le fragment i (à partir
    de 0) entre dans le XOR du n-ième fragment redondant.
    """
    # Les puissances de 2 sont traitées à part, elles produisent des motifs.
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
    """Découpe data et ajoute nb_redundant fragments de redondance.

    fragments[i] porte l'index i + 1 : TS004 numérote à partir de 1.
    """
    if frag_size <= 0 or not data:
        raise ValueError("image vide ou taille de fragment invalide")
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
    """Reconstruit l'image à partir des fragments reçus, dans n'importe quel ordre.

    Chaque fragment est une équation sur GF(2) : un masque (quels fragments
    d'origine il combine) et une valeur. On maintient un système échelonné ; quand
    il compte M équations indépendantes, l'image est connue.

    Version pédagogique : un vrai appareil utilise un algorithme à faible empreinte
    mémoire, mais le résultat est le même.
    """

    def __init__(self, session: Session):
        self.session = session
        self._rows: dict[int, tuple[int, int]] = {}  # pivot -> (masque, valeur)

    @property
    def complete(self) -> bool:
        return len(self._rows) == self.session.nb_frag

    def push(self, index: int, fragment: bytes) -> bool:
        """Ajoute le fragment d'index donné (à partir de 1). Renvoie complete."""
        m = self.session.nb_frag
        # Ne jamais faire confiance aux longueurs annoncées par le réseau : c'est
        # exactement ce contrôle qui manquait dans la CVE-2026-13480.
        if index < 1:
            raise ValueError("index de fragment invalide")
        if len(fragment) != self.session.frag_size:
            raise ValueError("taille de fragment inattendue")

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
        """L'image reconstruite, sans le bourrage."""
        if not self.complete:
            raise ValueError("fragments insuffisants pour reconstruire l'image")
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
