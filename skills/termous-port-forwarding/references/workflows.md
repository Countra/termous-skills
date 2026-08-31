# Port forwarding workflows

## Tool map

The forwarding domain exposes these six tools:

- `termous.forwarding.profiles.list`: list saved profiles without changing them.
- `termous.forwarding.profiles.get`: inspect one saved profile by `profile_id`.
- `termous.forwarding.instances.list`: list active Core-managed instances and their current metrics.
- `termous.forwarding.instances.get`: inspect one instance by `forward_id`, including a briefly retained failed instance.
- `termous.forwarding.instances.start`: request an approved start from one exact source.
- `termous.forwarding.instances.stop`: request an approved stop for one exact global instance.

The four read tools require `forwarding:read`. Start and stop require `forwarding:manage`. When status verification matters, ensure the client has both scopes before starting.

When a ready exact `TERMOUS_VERIFIED_RESOURCE` represents the referenced SSH source, use that `session_id` directly and skip `termous.sessions.list`. Otherwise, when the user has not supplied an exact source ID, call `termous.sessions.list` with `sessions:read` to resolve a connected `session_id`, or call `termous.hosts.list` and `termous.hosts.access_profiles.list` with `hosts:read` to resolve a saved Host and its SSH Profiles. Do not infer the focused tab, use an SFTP file-session ID, require another Skill to be installed, or open another SSH connection.

## Understand the forwarding direction

| Mode | Listener | Connection path | Target fields |
|---|---|---|---|
| `local` | Termous Core machine at `bind_host:bind_port` | local client -> Core listener -> SSH transport -> target reached from the remote SSH side | required |
| `remote` | SSH server side at `bind_host:bind_port` | remote client -> remote listener -> SSH transport -> target reached from the Termous Core side | required |
| `dynamic` | Termous Core machine at `bind_host:bind_port` | SOCKS5 client -> Core listener -> SSH transport -> per-request target reached from the remote SSH side | forbidden |

`bound_address` is the actual listener address after startup. For `remote`, it describes the remote listener; for `local` and `dynamic`, it describes the Core-side listener.

Dynamic mode implements unauthenticated SOCKS5 CONNECT. It does not accept `target_host` or `target_port`. Default to loopback and warn before any broader bind.

## Inspect saved profiles

1. Call `termous.forwarding.profiles.list` and resolve an exact profile by ID, name, mode, host, listener, and target.
2. Call `.profiles.get` when the exact configuration matters.
3. Treat a profile as a read-only saved definition. Starting it uses a snapshot and always produces a `background_profile` instance.
4. Do not include `name`, `description`, `mode`, bind fields, or target fields with `profile_id`.

Example:

```json
{
  "client_request_id": "req-forward-profile-1",
  "profile_id": "fp_example"
}
```

If the profile changes or is deleted while approval is pending, Termous refuses the original request. Reload it and ask the user to confirm a new logical start.

## Start from an existing SSH session

1. Use the ready exact verified SSH resource when it represents the requested source; otherwise resolve one exact connected SSH `session_id`. Do not use a local terminal or an SFTP file-session ID.
2. Confirm that ending this SSH session will also stop the `session` forward.
3. Supply the inline mode and addresses. `bind_port` is required and must be in the range 1 to 65535. `bind_host` defaults to `127.0.0.1`.
4. For `local` or `remote`, supply a non-empty `target_host` and a target port in the same range. For `dynamic`, omit both target fields.

Example local forward:

```json
{
  "client_request_id": "req-forward-session-1",
  "session_id": "ses_example",
  "name": "Database tunnel",
  "mode": "local",
  "bind_host": "127.0.0.1",
  "bind_port": 15432,
  "target_host": "127.0.0.1",
  "target_port": 5432
}
```

## Start a one-off background forward

1. Resolve one exact saved Host and inspect its access catalog. Use `host_id` only when the user wants that Host's default SSH Profile; use `ssh_profile_id` when the user chose a particular SSH Profile, endpoint, or username. Never send both.
2. Explain that Termous opens and owns a dedicated background SSH transport for this instance. It does not reuse an interactive session.
3. Supply the same inline mode and address fields used by a session start.
4. If the host is not yet trusted or its key changed, the instance enters `waiting_host_trust`; only the native Termous UI can decide it.

Example dynamic forward:

```json
{
  "client_request_id": "req-forward-background-1",
  "host_id": "host_example",
  "name": "Private SOCKS tunnel",
  "mode": "dynamic",
  "bind_host": "127.0.0.1",
  "bind_port": 1080
}
```

An exact non-default SSH Profile uses the same inline forwarding fields with `ssh_profile_id` in place of `host_id`. Reusing a `client_request_id` with a different selector is an idempotency conflict.

## Observe startup and traffic

The main statuses are `starting`, `waiting_host_trust`, `running`, `reconnecting`, `stopping`, `stopped`, and `failed`. Phases may further report queued work, session or authentication resolution, SSH dialing, Host Key waiting, listener startup, retry waiting, readiness, stopping, or failure.

1. Keep the returned `forward_id`.
2. Poll `.instances.get` at a reasonable interval while startup is in progress. Do not treat `progress=100` alone as proof of a usable tunnel; require `status=running` and `phase=ready`.
3. Preserve and report the returned `host_id` and actual `ssh_profile_id`. The resolved Profile is fixed for this instance; a later new `host_id` request may use a new default, so never project the current Host default onto an existing instance.
4. Report `bound_address`, `active_connections`, `total_connections`, `bytes_in`, and `bytes_out` only as observed counters.
5. If Host Key confirmation is required, stop polling aggressively and ask the user to inspect Termous.
6. If failed, report the safe status message and stable tool error when present. MCP intentionally does not expose raw internal failure text or a Host Key challenge ID.

## Stop an instance

1. List or get the exact instance immediately before stopping it.
2. Show its `forward_id`, name, mode, lifecycle, listener, target when applicable, and host or session identity.
3. Make clear that Core instances are global and may have been created outside this MCP client.
4. Generate a new `client_request_id` for this logical stop and call `.instances.stop` once.
5. `accepted=true` means the stop request was accepted. Active connections are closed as the listener and owned background transport shut down.
6. A stopped instance may disappear before a later `.get`; do not mistake the lack of durable history for evidence that it never existed.
