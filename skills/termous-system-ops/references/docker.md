# Docker 资源管理

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

## 镜像、数据卷和网络

新增资源与容器独立授权，管理权限不隐含读取权限。`termous.remoteops.docker.capability` 接受 `docker:read` 或下列任一资源读取权限；该共享探测不会授予容器访问权。仅使用当前 MCP 连接实际公布的工具。

| 权限 | 工具 |
| --- | --- |
| `docker:images:read` | `termous.remoteops.docker.images.list`、`termous.remoteops.docker.images.get` |
| `docker:images:manage` | `termous.remoteops.docker.images.action` |
| `docker:volumes:read` | `termous.remoteops.docker.volumes.list`、`termous.remoteops.docker.volumes.get` |
| `docker:volumes:manage` | `termous.remoteops.docker.volumes.create`、`termous.remoteops.docker.volumes.action` |
| `docker:networks:read` | `termous.remoteops.docker.networks.list`、`termous.remoteops.docker.networks.get` |
| `docker:networks:manage` | `termous.remoteops.docker.networks.create`、`termous.remoteops.docker.networks.action` |

列表接受 `session_id`、可选 `query`、`offset`、`limit`（默认 100、最多 500）。使用返回的完整镜像 ID（`sha256:` 加 64 位十六进制）或网络 ID（64 位十六进制）作为 `ref`；数据卷使用完整名称。详情只包含安全投影，不返回原始 inspect 或驱动私有选项。

写操作携带稳定的 `client_request_id`，默认逐次在 Termous 审批：

- 镜像 `action=tag` 需要 `tag`，使用显式仓库标签，如 `app:v2`；已有标签可能改为指向此镜像。`action=remove` 非强制删除镜像。
- 卷 `create` 需要 `name`，固定使用 local 驱动，不接受驱动选项；同名已有卷可能由 Docker 直接返回。卷 `action=remove` 会永久删除卷内数据，使用中的卷不强制删除。
- 网络 `create` 需要 `name`，固定使用 bridge 驱动；`internal=true` 表示内部网络，省略或 false 表示普通网络。
- 网络 `action=connect` 或 `disconnect` 需要 `container`，优先传完整容器 ID。Core 在审批前解析并绑定完整容器 ID。`action=remove` 非强制删除网络。

镜像和网络操作绑定完整 ID。数据卷没有不可变 ID，Core 在审批后复核创建时间、驱动及挂载位置；缺少创建时间或卷发生替换时拒绝执行。Docker 未提供卷删除 CAS，因此检查与执行之间不构成原子保证。

不支持 force、prune、任意驱动参数或 CLI 片段。不把缺失能力转成通用命令执行。`MCP_OPERATION_UNCERTAIN` 或 `DOCKER_RESOURCE_TIMEOUT` 后先用获授权的只读工具核对；不使用新请求 ID 自动重试。结果只确认该 Docker 操作完成，不证明应用健康或后续状态不会变化。
