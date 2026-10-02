"""The radio budget, recomputed.

The article's figures come from Abdelfadeel et al., "How to make Firmware Updates
over LoRaWAN Possible", arXiv 2002.08735. The study counts 51 bytes of firmware per
frame; this calculator also removes the real headers, and so finds slightly longer
durations. We check the order of magnitude, not equality.
"""

import pytest

from fuota.airtime import EU868, fragments_needed, session_duration, time_on_air

IMAGE_50K = 50 * 1024


def test_time_on_air_matches_the_reference_driver():
    # Value produced by SX1276GetLoRaTimeOnAirNumerator() from LoRaMac-node for
    # 64 bytes (51 + LoRaWAN header) at SF12, 125 kHz, without CRC.
    assert time_on_air(51, sf=12) == pytest.approx(2.793472)


def test_time_on_air_grows_with_the_spreading_factor():
    durations = [time_on_air(51, sf) for sf in range(7, 13)]
    assert durations == sorted(durations)


def test_a_50_kb_image_needs_a_thousand_frames_at_dr2():
    # The study's figure, with its assumption: 51 bytes of firmware per frame.
    assert fragments_needed(IMAGE_50K, frag_size=51) == 1004
    # With the TS004 fragment header, only 48 are left.
    assert fragments_needed(IMAGE_50K, frag_size=48) == 1067


def test_a_50_kb_image_takes_most_of_a_day_at_dr2():
    # The study reports about 17 hours for a single device.
    hours = session_duration(IMAGE_50K, EU868[2]) / 3600
    assert hours == pytest.approx(20.7, abs=0.1)


def test_dr0_is_tens_of_times_slower_than_dr5():
    # The study reports a factor close to 30.
    ratio = session_duration(IMAGE_50K, EU868[0]) / session_duration(IMAGE_50K, EU868[5])
    assert ratio == pytest.approx(34.5, abs=0.1)


def test_redundancy_adds_frames():
    assert fragments_needed(48_000, frag_size=48, redundancy=0.20) == 1200
