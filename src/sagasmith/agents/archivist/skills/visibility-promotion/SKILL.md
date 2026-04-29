---
name: visibility-promotion
allowed_agents: [archivist]
first_slice: true
implementation_surface: deterministic
description: Promotes vault page visibility (gm_only to foreshadowed to player_known) based on entity presence in narration; never demotes.
---

# Visibility Promotion

Promote vault page visibility one-way from `gm_only` to `foreshadowed` when an
entity is mentioned in player-visible text, and to `player_known` when the
entity is directly present in the active scene. Never demote visibility.
