---
name: rolling-summary-update
agent: archivist
first_slice: true
implementation_surface: llm
---

# Rolling Summary Update

At scene boundaries, update the campaign rolling summary with an LLM call that
retains only verifiable canonical facts and respects the configured token cap.
