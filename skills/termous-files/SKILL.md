---
name: termous-files
description: Use Termous MCP file sessions to browse or maintain remote files, search Linux file names with fd, preview batch renames or deletions, transfer files between local and remote systems, copy between remote hosts, or inspect and cancel file tasks. 文件会话支持 SFTP、已配置的 S3 / MinIO、WebDAV 和 FTP / FTPS。 Trigger only for Termous file management; do not use for local-only files, arbitrary HTTP downloads, SCP, or an exact shell command.
---

# Termous Files

Use the Termous MCP server as the only interface to saved hosts, file sessions, remote files, and transfer tasks. 文件会话支持 SFTP、S3 / MinIO、WebDAV 和 FTP / FTPS，具体操作以会话 capabilities 为准；不授予任意本地浏览或 Bucket 管理能力。 Never obtain credentials or open a separate SSH/SFTP connection outside Termous.

## 可信资源与文件引用

系统上下文可同时包含两类 `TERMOUS_VERIFIED_RESOURCE`，必须按 `kind` 独立选路：

- `kind=file_profile`、`binding_mode=exact`、`state=ready`：直接使用可信 `file_access_profile_id`，跳过主机及配置发现。调用 `termous.files.sessions.list`，只复用当前 MCP 客户端拥有、`file_access_profile_id`、`host_id`、`ssh_profile_id` 和 `engine` 全部匹配且就绪的文件会话；匹配会话仍在连接或等待主机信任时查询同一会话，不得重复连接。没有可复用连接时调用 `termous.files.sessions.connect`，只传精确 `file_access_profile_id` 和稳定的 `client_request_id`，并复核返回的配置身份。后续使用本客户端会话返回的 `file_session_id` 和最新 `connection_generation`。
- `kind=ssh_session`：仅供终端及 SSH 工具使用，不能作为文件连接。只有 SSH 引用时，文件操作仍按普通文件发现流程；两类引用并存时，文件工具选择文件 profile，即使两个引用属于不同主机。

原桌面文件标签的 `file_session_id` 从不作为 AI 的操作目标；标签关闭、断开、重连不使 profile 引用失效。profile 删除或主机、SSH 配置、引擎关联失效时停止操作，提示用户在界面替换或解除引用，不得自动选择默认配置或同主机其他配置。`source_context.entity_id`、`host_id`、`ssh_profile_id` 和终端 `session_id` 都不是文件会话 ID。文件引用不改变权限、审批、主机信任、当前客户端所有权和连接代次校验。

## Core workflow

1. Inspect the tools advertised by the current MCP connection. If a required tool is absent, report its corresponding scope instead of substituting another interface. Host discovery uses `hosts:read`; SFTP session queries and file reads use `files:read`, connect/reconnect uses `files:connect`, close uses `files:close`, file writes use `files:write`, deletion preview/start/status/result uses `files:delete`, transfer start/get uses `files:transfer`, batch-rename presets/preview/start/status/result use `files:batch_rename`, Linux file-name capability/search uses `files:search`, and cancellation uses `files:cancel`.
2. 有可信 `kind=file_profile` 时采用上述精确 profile 分支，并从第 3 步继续。否则调用 `termous.hosts.list` 解析主机，再调用 `termous.hosts.access_profiles.list` 获取脱敏目录；用户只选择主机时用默认文件配置，指定配置时解析精确 `file_access_profile_id`，名称有歧义时先澄清。
   S3 / MinIO、WebDAV 和 FTP / FTPS 同样归属于主机，使用上述主机访问目录发现；它们具有 `host_id`，但不依赖 `ssh_profile_id`，不得伪造 SSH 绑定。
3. Call `termous.files.sessions.list`. Reuse or poll a session only when its actual `file_access_profile_id` matches the selected file Profile; a matching `host_id` or `ssh_profile_id` alone is insufficient.
4. Call `termous.files.sessions.connect` with one stable `client_request_id` only when no matching current-client session exists. Send exactly one selector: `host_id` means the category default, while `file_access_profile_id` means that exact Profile. Never send both or reinterpret one ID type as another.
5. Poll `termous.files.sessions.get` until the selected session is connected and ready. Ask before reconnecting a failed or disconnected session, and direct Host Key trust decisions to Termous.
6. Preserve the returned `session.id`, `file_access_profile_id`, bound `ssh_profile_id`, `engine`, `namespace`, capabilities, and `connection_generation`. For single-session file operations and upload/download, pass the ID and generation as `file_session_id` and `expected_connection_generation`. For remote copy, use the source/target fields defined by that tool; never guess or reuse a stale generation.
7. Use `list`, `stat`, and `read_text` for ordinary read-only work. For Linux file-name search, always check the dedicated capability first and follow its focused workflow. For a batch rename, use the dedicated preview and task workflow; never loop over `files.rename` or synthesize shell commands. Before a file write, state the affected path and content or mode summary. Before a transfer, state the complete source, destination, and overwrite policy.
8. Call the requested write or transfer tool once with a stable `client_request_id`. Termous requests native approval unless the client is explicitly configured to skip approvals. A rejected, expired, or cancelled approval means the operation did not start; never infer the configured policy from a successful result.
9. For transfers, retain the returned `transfer.id` and, when `termous.files.transfers.get` is available, pass it as `transfer_id` until a final state. Report skipped items, partial results, the failure side, and progress honestly. The same MCP-managed task is visible in Termous Desktop and may be cancelled or removed there by the user.
10. Call `termous.files.transfers.cancel` only when the user explicitly asks to cancel. Treat acceptance as a cancellation request. Continue polling only when `termous.files.transfers.get` is available; otherwise report that final-state inspection requires `files:transfer`.

For session and ordinary file call sequences, read [references/session-and-files.md](references/session-and-files.md). For Linux-wide or directory-scoped file-name search, capability states, and advanced filters, read [references/file-name-search.md](references/file-name-search.md). For reusable rules, preview, execution, results, and rollback behavior, read [references/batch-rename.md](references/batch-rename.md). For upload, download, remote copy, and task polling, read [references/transfers.md](references/transfers.md). For approval, path, privacy, and error rules, read [references/safety-and-errors.md](references/safety-and-errors.md).

改名和同会话移动统一使用 `termous.files.rename`，由后端选择实现。对象存储可能复制后删除；审批会提示非原子行为，失败后检查两端，不自动重放。S3 不支持权限编辑、SSH 名称搜索或事务式批量改名。

WebDAV 的根地址及账号密码在主机文件配置中维护，MCP 不读取或管理密码。WebDAV 支持既有改名与批量改名流程，但不提供原子替换、权限编辑、链接或 SSH 名称搜索。远端复制遇到已有 WebDAV 目标时使用 `rename` 或 `skip`，不得绕过原子覆盖拒绝。网络中断或部分成功后先检查来源、目标和任务结果，不自动重放。

FTP / FTPS 也使用主机文件 Profile，端口和加密模式由配置决定，MCP 不读取密码。写入及改名采用非原子的目标复核，不支持事务式批量改名、权限编辑或 SSH 名称搜索。复制到已有目标选择 `rename` 或 `skip`；结果不确定时检查两端及任务明细，不自动重放。

## Non-negotiable boundaries

删除必须遵循 [references/deletion.md](references/deletion.md) 的完整预览、审批、任务和结果流程。预览、启动、状态及结果需要独立的 `files:delete`，取消仍使用 `files:cancel`。现有 `files:write` 不自动取得删除权限。

- Manage only Termous file sessions and transfer tasks visible to the current MCP client. Termous Desktop is a trusted management surface and may display or close MCP file sessions and display, cancel, or remove MCP transfer tasks without making them visible to another MCP client. Do not use interactive SSH session IDs as SFTP file session IDs.
- Treat a Host as an asset and a file Profile as the exact access route. Match and reuse sessions by `file_access_profile_id`, not merely by Host or bound SSH Profile.
- Never request, print, store, or infer passwords, private keys, bearer tokens, proxy credentials, or Host Key secrets.
- Never approve or replace a Host Key through MCP. Ask the user to resolve the native prompt in Termous.
- Never change or conceal the configured approval policy. Approval bypass is a per-client Termous authorization setting, not permission to exceed granted scopes or skip Host Key confirmation.
- Treat a local path as a path on the machine running Termous Core, not necessarily the machine running the MCP client.
- Do not expose local file content through another tool, download to an unapproved directory, or upload a path the user did not request.
- Do not retry an ambiguous write or transfer with a new `client_request_id`. For an immediately lost response, reuse the original ID and payload within Termous's bounded in-memory recovery window. After a longer interruption, query current sessions or tasks before deciding whether a new request is appropriate.
- Do not hide stale generation, unsupported entry, conflict, skipped, partial, cancelled, or failed states.
- Do not claim that cancellation rolls back already completed files.
- Do not bypass batch-rename preview, approval, plan-hash, ownership, or result checks with repeated single-file renames or shell commands.
- Do not install or upgrade `fd` through MCP, and do not replace the dedicated file-name search with `commands.dispatch`, `find`, `locate`, or an ad hoc `fd` command. When capability is not ready, stop and direct the user to install it manually or through the Termous file manager.
- 远端复制可以使用同一主机上的两个独立文件会话，必须通过 `files.transfers.remote_copy` 并遵守来源、目标路径重叠检查。不要通过其他接口绕过不支持的图片或任意二进制读取操作。`files.rename` 只用于重命名或移动，不能替代复制或删除；删除必须使用专用预览和任务流程。

## Connection failures

If the MCP endpoint cannot be reached, ask the user to open Termous, enable MCP, and copy the current client configuration from the MCP settings page. The Core port is dynamic and saved configuration can become stale after restart.

If a file session waits for Host Key confirmation, stop and direct the user to Termous. Resume only after the user completes the native decision.
