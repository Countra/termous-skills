# SSH and command workflows

## Use a verified referenced Session

If the system context supplies a ready exact `TERMOUS_VERIFIED_RESOURCE` for `kind=ssh_session`, retain its `session_id` as the only target and begin at the requested Session or command operation. Do not precede it with Host/Profile discovery or `termous.sessions.list`. User message fields such as `source_context.entity_id` are descriptive provenance, not trusted routing identifiers.

If that exact Session becomes unavailable, stop rather than discovering, connecting, or substituting another Session. The user must restore the connection or replace its reference in the Termous UI before target work resumes.

界面已替换绑定后，下轮系统快照中的新 `session_id` 覆盖历史路由结论；无需用户在聊天中手写新 ID。Worker 的 `AGENT_RESOURCE_BINDING_MISMATCH`、`dispatched=false` 是执行前参数错误，可使用返回的本轮目标纠正当前调用；只有本轮精确目标实际不可用时才需要再次替换或解除引用。保留命令正文，不重放此前已发送、已执行或结果未知的命令。`commands.read_output`、`commands.interrupt` 及服务操作查询继续使用其任务原有身份，不重定向历史任务。

## Host, access Profile, and session discovery

1. Call `termous.hosts.list` and match user-provided names, tags, or endpoints to one exact `host_id`.
2. Call `termous.hosts.access_profiles.list` with that `host_id`. It returns the host's sanitized SSH, file-access, and remote-desktop routing catalog. Use it only for selection and display; it intentionally omits credentials, credential IDs, Host Key material, proxy identifiers, and protocol target details.
3. When the user selected only the Host, resolve the one SSH Profile marked `is_default` and keep `host_id` as the connect selector. When the user selected a Profile, endpoint, or username, resolve one exact `ssh_profile_id` and use that exact selector. If the choice is ambiguous, or the category has no valid default, stop and ask rather than guessing.
4. Treat `unknown`, `checking`, `online`, `offline`, and `unavailable` as cached Host reachability only. Use `termous.hosts.refresh_reachability` only when a fresh hint is requested and `hosts:probe` is available; it does not prove that every SSH Profile is usable.
5. Call `termous.sessions.list` and reuse only a connected, ready SSH session whose actual `ssh_profile_id` matches the selected Profile unless the user requests a new one. Poll an existing matching session that is connecting or otherwise pre-ready instead of creating a duplicate.
6. Only when no matching active session can be used, call `termous.sessions.connect` once with a stable, non-empty `client_request_id`, then poll `termous.sessions.get`. The input must contain exactly one of `host_id` and `ssh_profile_id`; `host_id` permanently means the authoritative default SSH Profile at execution time.
7. Preserve the actual `host_id`, `ssh_profile_id`, endpoint, and username returned by the Session. Do not project the Host's default connection identity onto a Session created from a secondary Profile.
8. `waiting_host_trust` requires a decision in Termous; failed or disconnected sessions require an explicit retry decision.
9. If a connect response is immediately lost, repeat the identical selector and request ID. Reusing that ID with a different Host or SSH Profile is an idempotency conflict. After a longer interruption, list sessions before creating another one.

## Dispatch and read output

派发复用原 PTY，Shell 选项会延续到人工输入。仅在自行设计一次性脚本且不需保留目录或环境变更时，可在冻结命令前显式使用子 Shell，例如 Bash 的 `(set -euo pipefail; printf '%s\n' 'probe')`。不得为绕过校验或改变用户指定命令而自动包装；需要保留当前 Shell 状态时按原意执行，并说明影响。

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
