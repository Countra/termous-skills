# SSH and command workflows

## Host and session discovery

1. Call `termous.hosts.list` and match user-provided names, tags, or endpoints to one exact `host_id`.
2. Treat `unknown`, `checking`, `online`, `offline`, and `unavailable` as cached reachability only. Use `termous.hosts.refresh_reachability` only when a fresh hint is requested and `hosts:probe` is available.
3. Call `termous.sessions.list` and reuse only a connected, ready SSH session unless the user requests a new one. Poll an existing matching session that is connecting or otherwise pre-ready instead of creating a duplicate.
4. Only when no matching active session can be used, call `termous.sessions.connect` once with a stable, non-empty `client_request_id`, then poll `termous.sessions.get`.
5. `waiting_host_trust` requires a decision in Termous; failed or disconnected sessions require an explicit retry decision.
6. If a connect response is immediately lost, repeat the identical request with the same ID. After a longer interruption, list sessions before creating another one.

## Dispatch and read output

1. Freeze the exact command and ordered SSH `session_id` values. Reject multiline commands locally; do not rewrite, wrap, escape, split, or append shell syntax to make a command pass validation.
2. Confirm that `termous.commands.get` and `termous.commands.read_output` are available before dispatching, so the result can be verified.
3. State the exact command and targets, then call `termous.commands.dispatch` with one stable `client_request_id`.
4. Approval rejection, expiry, cancellation, or a busy command manager means the command was not queued. Do not loop or create a second request automatically.
5. Retain the returned `task_id` and poll `termous.commands.get` for task state. Its target `output_epoch` and `next_offset` describe the producer tail, not a consumer cursor; never use them for the first output read.
6. For each target, call `termous.commands.read_output` first without an epoch and with offset `"0"`. On later pages, use only the `epoch` and `next_offset` returned by the previous `read_output` response. Preserve offsets as decimal strings and decode only the returned encoding.
7. Stop reading a target only at `eof=true`. Report `gap` or `truncated` even if the visible text looks complete.
8. A completed task and a consumed output stream are separate facts. Report each target's final state and known exit code independently.

## Interrupt and close

1. Confirm whether the user wants the whole command task or one target interrupted.
2. Call `termous.commands.interrupt` once, then poll `termous.commands.get` until the affected target reaches a final state.
3. For session cleanup, inspect `owned_by_client` and show the exact host and `session_id`. A client with `sessions:close` can close any visible SSH session, including one created in the UI or by another MCP client; disclose that impact before calling `termous.sessions.close`, then re-list sessions to verify removal.
