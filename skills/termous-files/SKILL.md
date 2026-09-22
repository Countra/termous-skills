---
name: termous-files
description: Use Termous MCP file sessions to browse or maintain remote files, search Linux file names with fd, preview batch renames or deletions, transfer files between local and remote systems, copy between remote hosts, or inspect and cancel file tasks. File sessions support SFTP and configured S3 / MinIO, WebDAV, and FTP / FTPS profiles. Trigger only for Termous file management; do not use for local-only files, arbitrary HTTP downloads, SCP, or an exact shell command.
---

# Termous Files

Use the Termous MCP server as the only interface to saved hosts, file sessions, remote files, and transfer tasks. File sessions support SFTP, S3 / MinIO, WebDAV, and FTP / FTPS; available operations depend on the session's capabilities. They do not grant arbitrary local browsing or bucket management. Never obtain credentials or open a separate SSH/SFTP connection outside Termous.

## Verified resources and file references

The system context may contain both of the following `TERMOUS_VERIFIED_RESOURCE` kinds. Route each independently by `kind`:

- `kind=file_profile`, `binding_mode=exact`, `state=ready`: use the verified `file_access_profile_id` directly and skip host and profile discovery. Call `termous.files.sessions.list` and reuse only a ready file session owned by the current MCP client whose `file_access_profile_id`, `host_id`, `ssh_profile_id`, and `engine` all match. If a matching session is still connecting or waiting for Host Key trust, poll that same session rather than creating a duplicate connection. When no reusable connection exists, call `termous.files.sessions.connect` with only the exact `file_access_profile_id` and a stable `client_request_id`, then verify the returned profile identity. Use that client's returned `file_session_id` and latest `connection_generation` for subsequent operations.
- `kind=ssh_session`: use this only for terminal and SSH tools, never as a file connection. If only an SSH reference exists, file operations still use ordinary file discovery. When both reference kinds exist, file tools select the file profile even if the references belong to different hosts.

Never use the original desktop file tab's `file_session_id` as the AI's operation target. Closing, disconnecting, or reconnecting that tab does not invalidate its profile reference. If the profile is deleted or its host, SSH profile, or engine association becomes invalid, stop and ask the user to replace or remove the reference in the UI; do not automatically select a default or another profile on the same host. `source_context.entity_id`, `host_id`, `ssh_profile_id`, and a terminal `session_id` are not file session IDs. File references do not change permission, approval, Host Key trust, current-client ownership, or connection-generation checks.

## Core workflow

1. Inspect the tools advertised by the current MCP connection. If a required tool is absent, report its corresponding scope instead of substituting another interface. Host discovery uses `hosts:read`; File session queries and file reads use `files:read`, connect/reconnect uses `files:connect`, close uses `files:close`, file writes use `files:write`, deletion preview/start/status/result uses `files:delete`, transfer start/get uses `files:transfer`, batch-rename presets/preview/start/status/result use `files:batch_rename`, Linux file-name capability/search uses `files:search`, and cancellation uses `files:cancel`.
2. When a verified `kind=file_profile` is present, use the exact-profile branch above and continue from step 3. Otherwise, call `termous.hosts.list` to resolve the host, then `termous.hosts.access_profiles.list` to obtain the sanitized catalog. Use the default file profile when the user selected only a host; resolve the exact `file_access_profile_id` when a profile was specified. Clarify ambiguous names before proceeding.
   S3 / MinIO, WebDAV, and FTP / FTPS profiles also belong to hosts and are discovered through the same host access catalog. They have a `host_id` but do not depend on `ssh_profile_id`; never fabricate an SSH binding.
3. Call `termous.files.sessions.list`. Reuse or poll a session only when its actual `file_access_profile_id` matches the selected file Profile; a matching `host_id` or `ssh_profile_id` alone is insufficient.
4. Call `termous.files.sessions.connect` with one stable `client_request_id` only when no matching current-client session exists. Send exactly one selector: `host_id` means the category default, while `file_access_profile_id` means that exact Profile. Never send both or reinterpret one ID type as another.
5. Poll `termous.files.sessions.get` until the selected session is connected and ready. Ask before reconnecting a failed or disconnected session, and direct Host Key trust decisions to Termous.
6. Preserve the returned `session.id`, `file_access_profile_id`, bound `ssh_profile_id`, `engine`, `namespace`, capabilities, and `connection_generation`. For single-session file operations and upload/download, pass the ID and generation as `file_session_id` and `expected_connection_generation`. For remote copy, use the source/target fields defined by that tool; never guess or reuse a stale generation.
7. Use `list`, `stat`, and `read_text` for ordinary read-only work. For Linux file-name search, always check the dedicated capability first and follow its focused workflow. For a batch rename, use the dedicated preview and task workflow; never loop over `files.rename` or synthesize shell commands. Before a file write, state the affected path and content or mode summary. Before a transfer, state the complete source, destination, and overwrite policy.
8. Call the requested write or transfer tool once with a stable `client_request_id`. Termous requests native approval unless the client is explicitly configured to skip approvals. A rejected, expired, or cancelled approval means the operation did not start; never infer the configured policy from a successful result.
9. For transfers, retain the returned `transfer.id` and, when `termous.files.transfers.get` is available, pass it as `transfer_id` until a final state. Report skipped items, partial results, the failure side, and progress honestly. The same MCP-managed task is visible in Termous Desktop and may be cancelled or removed there by the user.
10. Call `termous.files.transfers.cancel` only when the user explicitly asks to cancel. Treat acceptance as a cancellation request. Continue polling only when `termous.files.transfers.get` is available; otherwise report that final-state inspection requires `files:transfer`.

For session and ordinary file call sequences, read [references/session-and-files.md](references/session-and-files.md). For Linux-wide or directory-scoped file-name search, capability states, and advanced filters, read [references/file-name-search.md](references/file-name-search.md). For reusable rules, preview, execution, results, and rollback behavior, read [references/batch-rename.md](references/batch-rename.md). For upload, download, remote copy, and task polling, read [references/transfers.md](references/transfers.md). For approval, path, privacy, and error rules, read [references/safety-and-errors.md](references/safety-and-errors.md).

Use `termous.files.rename` for both renaming and moving within a session; the backend selects the implementation. Object storage may copy and then delete, and the approval prompt identifies this non-atomic behavior. After failure, inspect both source and destination rather than replaying automatically. S3 does not support permission editing, SSH file-name search, or transactional batch rename.

Manage the WebDAV root URL, username, and password in the host's file profile; MCP does not read or manage passwords. WebDAV supports the existing rename and batch-rename workflows, but not atomic replacement, permission editing, links, or SSH file-name search. For remote copies to an existing WebDAV target, use `rename` or `skip`; do not bypass rejection of atomic overwrite. After a network interruption or partial success, inspect the source, destination, and task results before proceeding; do not replay automatically.

FTP / FTPS also uses a host file profile, which specifies the port and encryption mode; MCP does not read passwords. Writes and renames use non-atomic target revalidation. Transactional batch rename, permission editing, and SSH file-name search are unsupported. When copying to an existing target, choose `rename` or `skip`. If the result is uncertain, inspect both ends and the task details rather than replaying automatically.

## Non-negotiable boundaries

Deletion must follow the complete preview, approval, task, and result workflow in [references/deletion.md](references/deletion.md). Preview, start, status, and result tools require the separate `files:delete` scope; cancellation still uses `files:cancel`. Existing `files:write` access does not automatically grant deletion permission.

- Manage only Termous file sessions and transfer tasks visible to the current MCP client. Termous Desktop is a trusted management surface and may display or close MCP file sessions and display, cancel, or remove MCP transfer tasks without making them visible to another MCP client. Do not use interactive SSH session IDs as file session IDs.
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
- Remote copies may use two independent file sessions on the same host, but must go through `files.transfers.remote_copy` and its source/target path-overlap checks. Do not use other interfaces to bypass unsupported image or arbitrary binary reads. `files.rename` is only for renaming or moving, not a substitute for copying or deletion; deletion must use its dedicated preview and task workflow.

## Connection failures

If the MCP endpoint cannot be reached, ask the user to open Termous, enable MCP, and copy the current client configuration from the MCP settings page. The Core port is dynamic and saved configuration can become stale after restart.

If a file session waits for Host Key confirmation, stop and direct the user to Termous. Resume only after the user completes the native decision.
