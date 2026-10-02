"""Radio budget of a FUOTA session: how many frames, how much time.

The airtime of a frame follows the formula of Semtech's reference driver
(SX1276GetLoRaTimeOnAirNumerator, in LoRaMac-node). Payload sizes are those of the
EU868 band, taken from table I of the arXiv 2002.08735 study.
"""

import math
from dataclasses import dataclass

# LoRaWAN header around the payload: MHDR (1) + DevAddr (4) + FCtrl (1)
# + FCnt (2) + FPort (1) + MIC (4).
LORAWAN_OVERHEAD = 13

# Each TS004 fragment is preceded by a command byte and two index bytes: that
# much less for the firmware.
TS004_FRAGMENT_HEADER = 3


@dataclass(frozen=True)
class DataRate:
    name: str
    sf: int
    max_payload: int  # application bytes per frame


EU868 = {
    0: DataRate("DR0", 12, 51),
    1: DataRate("DR1", 11, 51),
    2: DataRate("DR2", 10, 51),
    3: DataRate("DR3", 9, 115),
    4: DataRate("DR4", 8, 222),
    5: DataRate("DR5", 7, 222),
}


def time_on_air(payload: int, sf: int, bw: int = 125_000) -> float:
    """Airtime, in seconds, of a LoRaWAN downlink of `payload` bytes."""
    t_sym = (1 << sf) / bw
    low_dr_optimize = 1 if t_sym >= 0.016 else 0  # mandatory at SF11 and SF12
    phy_payload = payload + LORAWAN_OVERHEAD
    # Downlink: explicit header, no CRC, coding rate 4/5, preamble of 8.
    bits = 8 * phy_payload - 4 * sf + 28
    symbols = 8 + max(math.ceil(bits / (4 * (sf - 2 * low_dr_optimize))) * 5, 0)
    return (8 + 4.25 + symbols) * t_sym


def fragments_needed(image_size: int, frag_size: int, redundancy: float = 0.0) -> int:
    """Number of frames to transmit, redundancy included."""
    m = math.ceil(image_size / frag_size)
    return m + math.ceil(m * redundancy)


def session_duration(
    image_size: int,
    dr: DataRate,
    redundancy: float = 0.0,
    duty_cycle: float = 0.01,
    frag_size: int | None = None,
) -> float:
    """Minimum duration, in seconds, to broadcast the image under the duty-cycle limit."""
    if frag_size is None:
        frag_size = dr.max_payload - TS004_FRAGMENT_HEADER
    n = fragments_needed(image_size, frag_size, redundancy)
    return n * time_on_air(frag_size + TS004_FRAGMENT_HEADER, dr.sf) / duty_cycle
