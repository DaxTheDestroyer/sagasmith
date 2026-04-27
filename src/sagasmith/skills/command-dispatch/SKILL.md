---
name: command-dispatch
description: Parse and dispatch slash commands to registered handlers using the TUI CommandRegistry.
allowed_agents: ["*"]
implementation_surface: deterministic
first_slice: true
success_signal: Every supported slash command invokes its registered handler; unknown commands surface a friendly "unknown command" message.
---
# Command Dispatch

## When to Activate
When a player input starts with `/` in the Textual shell.

## Procedure
The TUI layer (Plan 03-03) handles this via `CommandRegistry.dispatch(app, line)`.
This skill exists as an audit reference.

## Deterministic Handler
Module: `sagasmith.tui.commands.registry`.
Class: `CommandRegistry`.

## Failure Handling
Unknown commands emit a player-visible narration line and log nothing else.
