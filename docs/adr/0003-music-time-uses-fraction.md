# ADR 0003: Musical time uses Fraction

- Status: Accepted
- Date: 2026-07-21

## Context

Physical audio time is naturally measured in seconds, but notation requires exact equality at beats, tuplets, barlines, ties, and export divisions. Binary floating-point values cannot reliably close measures.

## Decision

Use `float` only for physical seconds at the transcription boundary. Convert score positions and durations to `fractions.Fraction`; serialize fractions as explicit numerator/denominator fields when project persistence is introduced.

## Alternatives

- Float beats with tolerances: rejected because tolerances leak into every music rule.
- Fixed integer ticks as the domain: rejected because one resolution cannot represent every future tuplet without conversion constraints.
- Decimal: rejected because it is still a base-10 approximation for many musical ratios.

## Consequences

Adapters must deliberately convert to MusicXML divisions and MIDI ticks and reject unrepresentable values. Deterministic measure closure and equality become straightforward.
