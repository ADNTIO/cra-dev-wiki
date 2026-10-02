"""Le budget radio, recalculé.

Les chiffres de l'article viennent d'Abdelfadeel et al., « How to make Firmware
Updates over LoRaWAN Possible », arXiv 2002.08735. L'étude compte 51 octets de
firmware par trame ; ce calculateur retire en plus les en-têtes réels, et trouve
donc des durées un peu plus longues. On vérifie l'ordre de grandeur, pas l'égalité.
"""

import pytest

from fuota.airtime import EU868, fragments_needed, session_duration, time_on_air

IMAGE_50K = 50 * 1024


def test_time_on_air_matches_the_reference_driver():
    # Valeur produite par SX1276GetLoRaTimeOnAirNumerator() de LoRaMac-node pour
    # 64 octets (51 + en-tête LoRaWAN) à SF12, 125 kHz, sans CRC.
    assert time_on_air(51, sf=12) == pytest.approx(2.793472)


def test_time_on_air_grows_with_the_spreading_factor():
    durations = [time_on_air(51, sf) for sf in range(7, 13)]
    assert durations == sorted(durations)


def test_a_50_kb_image_needs_a_thousand_frames_at_dr2():
    # Le chiffre de l'étude, avec son hypothèse : 51 octets de firmware par trame.
    assert fragments_needed(IMAGE_50K, frag_size=51) == 1004
    # Avec l'en-tête de fragment TS004, il n'en reste que 48.
    assert fragments_needed(IMAGE_50K, frag_size=48) == 1067


def test_a_50_kb_image_takes_most_of_a_day_at_dr2():
    # L'étude annonce environ 17 heures pour un seul appareil.
    hours = session_duration(IMAGE_50K, EU868[2]) / 3600
    assert hours == pytest.approx(20.7, abs=0.1)


def test_dr0_is_tens_of_times_slower_than_dr5():
    # L'étude annonce un facteur proche de 30.
    ratio = session_duration(IMAGE_50K, EU868[0]) / session_duration(IMAGE_50K, EU868[5])
    assert ratio == pytest.approx(34.5, abs=0.1)


def test_redundancy_adds_frames():
    assert fragments_needed(48_000, frag_size=48, redundancy=0.20) == 1200
