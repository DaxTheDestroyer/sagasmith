---
name: schema-validation
description: Validate any dict or model payload against its Pydantic schema before persistence or LLM emission.
allowed_agents: ["*"]
implementation_surface: deterministic
first_slice: true
success_signal: Every persisted or LLM-boundary payload is validated; invalid payloads raise SchemaModel.ValidationError before any I/O.
---
# Schema Validation

## When to Activate
Before persisting any dict to SQLite, before emitting any payload to an LLM, or
when consuming an LLM response that claims to be structured output.

## Procedure
Use `pydantic.TypeAdapter(Model).validate_python(payload)` or
`Model.model_validate(payload)`. On failure, raise immediately — never
persist a partially-validated payload.

## Deterministic Handler
Module: `sagasmith.schemas` (each model has `.model_validate` / `.model_dump`).
Helper: `pydantic.TypeAdapter`.

## Failure Handling
Log `ValidationError` with redacted details; do NOT retry without a fresh
payload. Re-raise to the caller.
