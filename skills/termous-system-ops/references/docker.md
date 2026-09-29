# Docker Resource Management

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

## Images, volumes, and networks

These resources are authorized separately from containers, and manage Scopes do not imply read Scopes. `termous.remoteops.docker.capability` accepts `docker:read` or any resource read Scope below; this shared probe does not grant container access. Use only tools advertised by the current MCP connection.

| Scope | Tools |
| --- | --- |
| `docker:images:read` | `termous.remoteops.docker.images.list`, `termous.remoteops.docker.images.get` |
| `docker:images:manage` | `termous.remoteops.docker.images.action` |
| `docker:volumes:read` | `termous.remoteops.docker.volumes.list`, `termous.remoteops.docker.volumes.get` |
| `docker:volumes:manage` | `termous.remoteops.docker.volumes.create`, `termous.remoteops.docker.volumes.action` |
| `docker:networks:read` | `termous.remoteops.docker.networks.list`, `termous.remoteops.docker.networks.get` |
| `docker:networks:manage` | `termous.remoteops.docker.networks.create`, `termous.remoteops.docker.networks.action` |

List calls accept `session_id` and optional `query`, `offset`, and `limit` (default 100, maximum 500). Use the returned full image ID (`sha256:` followed by 64 hexadecimal digits) or network ID (64 hexadecimal digits) as `ref`; use the full name for a volume. Detail responses contain only a safe projection, not raw inspect output or private driver options.

Mutations require a stable `client_request_id` and per-call Termous approval by default:

- Image `action=tag` requires `tag`; use an explicit repository tag such as `app:v2`. An existing tag may be redirected to this image. `action=remove` removes an image without forcing deletion.
- Volume `create` requires `name`, uses the local driver, and accepts no driver options. Docker may return an existing volume with the same name. Volume `action=remove` permanently deletes its data and does not force removal of a volume in use.
- Network `create` requires `name` and uses the bridge driver. `internal=true` creates an internal network; omitting it or using false creates a regular network.
- Network `action=connect` or `disconnect` requires `container`; prefer the full container ID. Core resolves and binds the full container ID before approval. `action=remove` removes a network without forcing deletion.

Image and network operations bind to full IDs. Volumes have no immutable ID, so Core rechecks creation time, driver, and mount location after approval. It rejects execution if creation time is missing or the volume has been replaced. Docker provides no compare-and-swap operation for volume removal, so verification and execution are not atomic.

Force, prune, arbitrary driver parameters, and CLI fragments are unsupported. Do not replace missing capabilities with general command execution. After `MCP_OPERATION_UNCERTAIN` or `DOCKER_RESOURCE_TIMEOUT`, verify with authorized read-only tools first; do not retry automatically with a new request ID. A result confirms only completion of that Docker operation, not application health or an unchanging future state.
