"""A simulated radio link that loses frames."""

import random
from collections.abc import Iterator


def transmit(fragments: list[bytes], loss_rate: float, seed: int = 0) -> Iterator[tuple[int, bytes]]:
    """Broadcasts the fragments and returns those that arrive, with their index (from 1)."""
    rng = random.Random(seed)
    for index, fragment in enumerate(fragments, start=1):
        if rng.random() >= loss_rate:
            yield index, fragment
