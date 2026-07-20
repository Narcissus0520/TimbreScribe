"""Built-in transposing-instrument profile catalog."""

from __future__ import annotations

from timbrescribe.domain.score import InstrumentProfile, PitchRange

_PROFILES = (
    InstrumentProfile(
        "piano",
        "Piano",
        "keyboard",
        0,
        False,
        "grand",
        2,
        PitchRange(21, 108),
        PitchRange(21, 108),
        0,
        0,
        0,
        "grand-staff",
    ),
    InstrumentProfile(
        "flute",
        "Flute",
        "woodwind",
        73,
        False,
        "treble",
        1,
        PitchRange(60, 96),
        PitchRange(60, 96),
        0,
        0,
        0,
        "single-staff",
    ),
    InstrumentProfile(
        "clarinet-bb",
        "B-flat Clarinet",
        "woodwind",
        71,
        False,
        "treble",
        1,
        PitchRange(50, 94),
        PitchRange(48, 92),
        -1,
        -2,
        0,
        "single-staff",
    ),
    InstrumentProfile(
        "trumpet-bb",
        "B-flat Trumpet",
        "brass",
        56,
        False,
        "treble",
        1,
        PitchRange(54, 82),
        PitchRange(52, 80),
        -1,
        -2,
        0,
        "single-staff",
    ),
    InstrumentProfile(
        "alto-sax-eb",
        "E-flat Alto Saxophone",
        "woodwind",
        65,
        False,
        "treble",
        1,
        PitchRange(49, 87),
        PitchRange(40, 78),
        -5,
        -9,
        0,
        "single-staff",
    ),
    InstrumentProfile(
        "tenor-sax-bb",
        "B-flat Tenor Saxophone",
        "woodwind",
        66,
        False,
        "treble",
        1,
        PitchRange(49, 87),
        PitchRange(35, 73),
        -1,
        -2,
        -1,
        "single-staff",
    ),
    InstrumentProfile(
        "horn-f",
        "Horn in F",
        "brass",
        60,
        False,
        "treble",
        1,
        PitchRange(42, 84),
        PitchRange(35, 77),
        -4,
        -7,
        0,
        "single-staff",
    ),
)

INSTRUMENT_PROFILES = {profile.id: profile for profile in _PROFILES}


def get_instrument_profile(profile_id: str) -> InstrumentProfile:
    try:
        return INSTRUMENT_PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown instrument profile: {profile_id}") from exc
