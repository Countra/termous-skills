---
name: termous-sftp
description: Use Termous MCP SFTP sessions to browse or maintain files on saved SSH hosts, transfer files between the Termous Core machine and a remote host, copy between remote hosts, or inspect and cancel transfer tasks. Trigger only for Termous-managed SFTP work; do not use for local-only files, HTTP/S3 transfers, SCP, or an exact shell command.
---

# Termous SFTP

Use the Termous MCP server as the only interface to saved hosts, SFTP file sessions, remote files, and transfer tasks. Never obtain credentials or open a separate SSH/SFTP connection outside Termous.

## Core workflow

1. Inspect the tools advertised by the current MCP connection. If a required tool is absent, report its corresponding scope instead of substituting another interface. Host discovery uses `hosts:read`; SFTP session queries and file reads use `sftp:read`, connect/reconnect uses `sftp:connect`, close uses `sftp:close`, file writes use `sftp:write`, transfer start/get uses `sftp:transfer`, and cancellation uses `sftp:cancel`.
2. Call `termous.hosts.list` to resolve saved hosts. Resolve ambiguous names with the user before creating a file session.
3. Call `termous.sftp.sessions.list`. Reuse a ready session for the exact requested host, keep polling a connecting or pre-ready session, and ask before calling `termous.sftp.sessions.reconnect` for a failed or disconnected session. Call `termous.sftp.sessions.connect` with one stable `client_request_id` only when no current-client session matches that host.
4. Poll `termous.sftp.sessions.get` until the selected session is connected and ready. If Host Key trust is required, ask the user to act in Termous.
5. Preserve the returned `session.id` and `connection_generation`. For single-session file operations and upload/download, pass them as `file_session_id` and `expected_connection_generation`. For remote copy, use the source/target session and generation fields defined by that tool; never guess or reuse a stale generation.
6. Use `list`, `stat`, and `read_text` for read-only work. Before a file write, state the affected path and content or mode summary. Before a transfer, state the complete source, destination, and overwrite policy.
7. Call the requested write or transfer tool once with a stable `client_request_id`. Termous requests native approval unless the client is explicitly configured to skip approvals. A rejected, expired, or cancelled approval means the operation did not start; never infer the configured policy from a successful result.
8. For transfers, retain the returned `transfer.id` and, when `termous.sftp.transfers.get` is available, pass it as `transfer_id` until a final state. Report skipped items, partial results, the failure side, and progress honestly. The same MCP-managed task is visible in Termous Desktop and may be cancelled or removed there by the user.
9. Call `termous.sftp.transfers.cancel` only when the user explicitly asks to cancel. Treat acceptance as a cancellation request. Continue polling only when `termous.sftp.transfers.get` is available; otherwise report that final-state inspection requires `sftp:transfer`.

For session and file call sequences, read [references/session-and-files.md](references/session-and-files.md). For upload, download, remote copy, and task polling, read [references/transfers.md](references/transfers.md). For approval, path, privacy, and error rules, read [references/safety-and-errors.md](references/safety-and-errors.md).

## Non-negotiable boundaries

- Manage only SFTP file sessions and transfer tasks visible to the current MCP client. Termous Desktop is a trusted management surface and may display or close MCP file sessions and display, cancel, or remove MCP transfer tasks without making them visible to another MCP client. Do not use interactive SSH session IDs as SFTP file session IDs.
- Never request, print, store, or infer passwords, private keys, bearer tokens, proxy credentials, or Host Key secrets.
- Never approve or replace a Host Key through MCP. Ask the user to resolve the native prompt in Termous.
- Never change or conceal the configured approval policy. Approval bypass is a per-client Termous authorization setting, not permission to exceed granted scopes or skip Host Key confirmation.
- Treat a local path as a path on the machine running Termous Core, not necessarily the machine running the MCP client.
- Do not expose local file content through another tool, download to an unapproved directory, or upload a path the user did not request.
- Do not retry an ambiguous write or transfer with a new `client_request_id`. For an immediately lost response, reuse the original ID and payload within Termous's bounded in-memory recovery window. After a longer interruption, query current sessions or tasks before deciding whether a new request is appropriate.
- Do not hide stale generation, unsupported entry, conflict, skipped, partial, cancelled, or failed states.
- Do not claim that cancellation rolls back already completed files.
- Do not use unsupported deletion, same-host copy, image, or arbitrary binary-read operations through another interface. `files.rename` may rename or move an entry within one file session, but it is not a copy or delete substitute.

## Connection failures

If the MCP endpoint cannot be reached, ask the user to open Termous, enable MCP, and copy the current client configuration from the MCP settings page. The Core port is dynamic and saved configuration can become stale after restart.

If a file session waits for Host Key confirmation, stop and direct the user to Termous. Resume only after the user completes the native decision.
