---
name: termous-port-forwarding
description: Use Termous MCP to inspect saved forwarding profiles and Core-managed instances or start and stop local, remote, and dynamic forwarding through a saved Host default, an exact SSH access Profile, or a Termous SSH session. Trigger only for operating a Termous-managed tunnel or SOCKS5 proxy; do not use for conceptual questions or requests to run local ssh -L, -R, or -D commands.
---

# Termous Port Forwarding

Use Termous MCP as the only interface to saved forwarding profiles and live forwarding instances. Do not open a separate SSH connection or recreate a forward with shell commands.

## Core workflow

1. Inspect saved profiles with `termous.forwarding.profiles.list` and `.get`, or inspect Core-managed instances with `termous.forwarding.instances.list` and `.get`.
2. Resolve one exact start source:
   - `profile_id` starts the saved profile as `background_profile` and accepts no inline forwarding fields;
   - `session_id` reuses one connected SSH session and creates a `session` forward;
   - `host_id` opens a dedicated one-off background connection through that Host's default SSH Profile;
   - `ssh_profile_id` opens the one-off background connection through that exact SSH Profile.
3. For an inline start, choose `local`, `remote`, or `dynamic`; confirm the listener, network direction, and exposure before proceeding. `bind_host` defaults to `127.0.0.1` when omitted.
4. State the exact source, mode, listener, target when applicable, and lifecycle. Generate one stable `client_request_id` for the logical start and call `termous.forwarding.instances.start` once.
5. The start passes through the Termous approval gate. A client explicitly configured for approval bypass executes the granted operation without a pending decision; bypass never adds scopes or approves a Host Key.
6. Retain the returned `forward_id` and poll `.get` until the instance is running, waiting for Host Key trust, or has failed. A returned start record does not prove that the listener is ready.
7. Before stopping, inspect and identify the exact global instance. Use a new stable `client_request_id`, call `termous.forwarding.instances.stop` once, and treat `accepted` as a stop request rather than durable history.

For exact mode directions, start payloads, and status handling, read [references/workflows.md](references/workflows.md). For approval, network exposure, global ownership, Host Key, idempotency, and lifecycle rules, read [references/safety-and-lifecycle.md](references/safety-and-lifecycle.md).

## Non-negotiable boundaries

- Saved forwarding profiles are read-only through MCP. Do not emulate profile creation, editing, or deletion with another tool.
- Use exactly one source selector: `profile_id`, `session_id`, `host_id`, or `ssh_profile_id`. For an inline background start, `host_id` means the default SSH Profile and `ssh_profile_id` means one exact Profile. Never combine selectors or silently switch source or lifecycle after confirmation.
- `dynamic` is an unauthenticated SOCKS5 listener. Never expose it beyond loopback without explicit user intent and a clear warning.
- Forward instances are global to Termous Core, not owned by an MCP client. A stop can affect an instance created in the UI or through another client.
- Never approve, replace, or conceal a Host Key decision. Direct the user to the native Termous prompt.
- Never infer success from approval or start acceptance. Report the observed status, phase, bound address, and any short-lived failure state.
- Never retry an ambiguous start or stop with a new `client_request_id`. Reuse the identical ID and payload only for immediate recovery.
- Use only tools advertised by the current MCP connection. If a required Tool is absent, explain the missing Scope or compatibility issue instead of falling back to commands; after a Scope change, reconnect MCP so its Tool list is rebuilt.
