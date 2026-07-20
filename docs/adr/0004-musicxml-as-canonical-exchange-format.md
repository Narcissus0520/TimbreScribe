# ADR 0004: MusicXML as canonical exchange format

- Status: Accepted
- Date: 2026-07-21

## Context

The application needs an editable format that can preserve common notation and interoperate with notation tools. PDF and images are presentation formats; MIDI does not preserve enough engraving semantics.

## Decision

MusicXML 4.0 `score-partwise` is the canonical editable exchange format. It is derived deterministically from the internal score and structurally validated before export. MIDI remains a playback/exchange adapter, not the score source of truth.

## Alternatives

- MIDI as canonical: rejected because spelling, rests, ties, voices, and engraving metadata are incomplete.
- PDF/SVG as canonical: rejected because they are not practical editable score models.
- Directly mutating MusicXML as the domain: rejected because editing and invariant checks need typed musical concepts.

## Consequences

The project maintains an internal score model plus a tested MusicXML adapter. Future release validation must add the official schema and Verovio/MuseScore round trips without enabling external XML entities.
