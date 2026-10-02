"""Un lien radio simulé, qui perd des trames."""

import random
from collections.abc import Iterator


def transmit(fragments: list[bytes], loss_rate: float, seed: int = 0) -> Iterator[tuple[int, bytes]]:
    """Diffuse les fragments et rend ceux qui arrivent, avec leur index (à partir de 1)."""
    rng = random.Random(seed)
    for index, fragment in enumerate(fragments, start=1):
        if rng.random() >= loss_rate:
            yield index, fragment
