---
name: rolling-summary-update
allowed_agents: [archivist]
first_slice: true
implementation_surface: prompted
description: Updates campaign rolling summary at scene boundaries using LLM; retains canonical facts within token cap.
---

# Rolling Summary Update

At scene boundaries, update the campaign rolling summary with an LLM call that
retains only verifiable canonical facts and respects the configured token cap.
