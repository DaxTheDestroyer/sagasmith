---
name: visibility-promotion
agent: archivist
first_slice: true
implementation_surface: deterministic
---

# Visibility Promotion

Promote vault page visibility one-way from `gm_only` to `foreshadowed` when an
entity is mentioned in player-visible text, and to `player_known` when the
entity is directly present in the active scene. Never demote visibility.
