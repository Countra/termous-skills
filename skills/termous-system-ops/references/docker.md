# Docker Containers

Use these tools only with an exact connected Linux SSH `session_id`.

## Tools and Scopes

Reads require `docker:read`:

- `termous.remoteops.docker.capability`
- `termous.remoteops.docker.containers.list`
- `termous.remoteops.docker.containers.get`
- `termous.remoteops.docker.containers.stats`
- `termous.remoteops.docker.containers.logs`

Mutations require `docker:manage` and native approval unless approval bypass is explicitly configured:

- `termous.remoteops.docker.containers.action`

## Capability and discovery

1. Call `termous.remoteops.docker.capability` before assuming the Docker CLI, daemon, or current-user access is available.
2. If the capability is unavailable, report its structured status and warnings. Do not substitute the Docker CLI through a shell command.
3. Use `termous.remoteops.docker.containers.list` to find the target. It supports query, state, health, and mapped-port filters and a limit up to 500.
4. Prefer the returned full container ID for subsequent calls. Names and short IDs can become ambiguous or be rebound.

## Detail, stats, and logs

- Call `termous.remoteops.docker.containers.get` for mounts, networks, labels, restart policy, arguments, redacted environment entries, optional stats, and a limited log preview. `log_tail` is capped at 1000.
- Call `termous.remoteops.docker.containers.stats` for one point-in-time CPU, memory, I/O, and PID snapshot. It is not a live monitor.
- Call `termous.remoteops.docker.containers.logs` for a bounded tail. `tail` is capped at 1000 and `timestamps` controls Docker timestamps.

Container detail previews and log responses are bounded to 256 KiB of text. Preserve redacted environment values exactly as returned, never attempt to reconstruct them, and always report `logs_truncated` or `truncated` when true. Mount sources, labels, arguments, and logs may contain sensitive or untrusted remote data; return only what the user's task requires.

## Container actions

Supported actions are exactly:

- `start`
- `stop`
- `restart`
- `pause`
- `unpause`

Workflow:

1. Read fresh container detail and confirm the exact session, full container ID, current state, and action.
2. Use `timeout_seconds` only where the selected stop or restart behavior needs it, and keep it between 0 and 20 seconds.
3. Generate one stable `client_request_id` and call `termous.remoteops.docker.containers.action` once.
4. Termous resolves the supplied reference and binds the approved operation to the full container ID, preventing a later name rebind from changing the target.
5. Interpret `attempted=true` as an attempted Docker action, then re-read the container to verify the resulting state when verification matters.

Do not choose a container from a partial name alone when more than one result matches. Do not claim that an accepted action proves application health inside the container.
