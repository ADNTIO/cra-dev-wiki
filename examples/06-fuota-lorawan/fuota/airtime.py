"""Budget radio d'une session FUOTA : combien de trames, combien de temps.

Le temps d'émission d'une trame suit la formule du pilote de référence Semtech
(SX1276GetLoRaTimeOnAirNumerator, dans LoRaMac-node). Les tailles de charge utile
sont celles de la bande EU868, reprises du tableau I de l'étude arXiv 2002.08735.
"""

import math
from dataclasses import dataclass

# En-tête LoRaWAN autour de la charge utile : MHDR (1) + DevAddr (4) + FCtrl (1)
# + FCnt (2) + FPort (1) + MIC (4).
LORAWAN_OVERHEAD = 13

# Chaque fragment TS004 est précédé d'un octet de commande et de deux octets
# d'index : c'est autant de moins pour le firmware.
TS004_FRAGMENT_HEADER = 3


@dataclass(frozen=True)
class DataRate:
    name: str
    sf: int
    max_payload: int  # octets applicatifs par trame


EU868 = {
    0: DataRate("DR0", 12, 51),
    1: DataRate("DR1", 11, 51),
    2: DataRate("DR2", 10, 51),
    3: DataRate("DR3", 9, 115),
    4: DataRate("DR4", 8, 222),
    5: DataRate("DR5", 7, 222),
}


def time_on_air(payload: int, sf: int, bw: int = 125_000) -> float:
    """Durée d'émission, en secondes, d'un downlink LoRaWAN de `payload` octets."""
    t_sym = (1 << sf) / bw
    low_dr_optimize = 1 if t_sym >= 0.016 else 0  # obligatoire à SF11 et SF12
    phy_payload = payload + LORAWAN_OVERHEAD
    # Downlink : en-tête explicite, pas de CRC, taux de codage 4/5, préambule de 8.
    bits = 8 * phy_payload - 4 * sf + 28
    symbols = 8 + max(math.ceil(bits / (4 * (sf - 2 * low_dr_optimize))) * 5, 0)
    return (8 + 4.25 + symbols) * t_sym


def fragments_needed(image_size: int, frag_size: int, redundancy: float = 0.0) -> int:
    """Nombre de trames à émettre, redondance comprise."""
    m = math.ceil(image_size / frag_size)
    return m + math.ceil(m * redundancy)


def session_duration(
    image_size: int,
    dr: DataRate,
    redundancy: float = 0.0,
    duty_cycle: float = 0.01,
    frag_size: int | None = None,
) -> float:
    """Durée minimale, en secondes, pour diffuser l'image sous la limite de temps d'émission."""
    if frag_size is None:
        frag_size = dr.max_payload - TS004_FRAGMENT_HEADER
    n = fragments_needed(image_size, frag_size, redundancy)
    return n * time_on_air(frag_size + TS004_FRAGMENT_HEADER, dr.sf) / duty_cycle
