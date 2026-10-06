# SSH and command workflows

## Use a verified referenced Session

If the system context supplies a ready exact `TERMOUS_VERIFIED_RESOURCE` for `kind=ssh_session`, retain its `session_id` as the only target and begin at the requested Session or command operation. Do not precede it with Host/Profile discovery or `termous.sessions.list`. User message fields such as `source_context.entity_id` are descriptive provenance, not trusted routing identifiers.

If that exact Session becomes unavailable, stop rather than discovering, connecting, or substituting another Session. The user must restore the connection or replace its reference in the Termous UI before target work resumes.

After a binding is replaced in the UI, the new `session_id` in the next run's system snapshot takes precedence over historical routing conclusions; the user does not need to type the new ID in chat. The Worker's `AGENT_RESOURCE_BINDING_MISMATCH` with `dispatched=false` is an argument error detected before execution. Correct the current call using the current run's target returned in the error. Ask the user to replace or remove the reference again only if that exact target is actually unavailable. Preserve the command text, and do not replay commands that were previously sent, executed, or left with an unknown result. `commands.read_output`, `commands.interrupt`, and service-operation queries must retain each task's original identity rather than redirect historical tasks.

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

Dispatch reuses the original PTY, so shell options also affect subsequent user input. When composing a one-off script that does not need to preserve directory or environment changes, an explicit subshell may be chosen before freezing the command, for example Bash's `(set -euo pipefail; printf '%s\n' 'probe')`. Do not automatically wrap a command to bypass validation or alter a user-specified command. When shell state must persist, execute the command as intended and explain its effects.

1. Freeze the exact command and ordered SSH `session_id` values. Reject multiline commands locally; do not rewrite, wrap, escape, split, or append shell syntax to make a command pass validation.
2. Confirm that `termous.commands.get` and `termous.commands.read_output` are available before dispatching, so the result can be verified.
3. State the exact command and targets, then call `termous.commands.dispatch` with one stable `client_request_id`.
4. 审批拒绝、过期、取消或任务容量超限表示本次请求未被受理；不要循环重试或自动创建新的请求。返回 `queued` 的目标已经受理，正在其 SSH 会话内部等待，继续查询原任务即可。
5. Retain the returned `task_id` and poll `termous.commands.get` for task state. Its target `output_epoch` and `next_offset` describe the producer tail, not a consumer cursor; never use them for the first output read.
6. For each target, call `termous.commands.read_output` first without an epoch and with offset `"0"`. On later pages, use only the `epoch` and `next_offset` returned by the previous `read_output` response. Preserve offsets as decimal strings and decode only the returned encoding.
7. Stop reading a target only at `eof=true`. Report `gap` or `truncated` even if the visible text looks complete.
8. A completed task and a consumed output stream are separate facts. Report each target's final state and known exit code independently.

同一 SSH 会话的托管命令按受理顺序逐条执行，不同 SSH 会话可并行。多个 AI 会话的多条命令可以交错，整轮 AI 不独占终端；需要依赖 cwd 或环境状态时，应考虑其他命令可能改变共享 Shell。人工输入或远控交互占用终端会明确拒绝执行，不应把占用错误当作自动重试信号。断线或连接换代后，旧目标不会自动投递到新连接。

命令创建回执丢失时，保留原始 `client_request_id` 和完整参数。只使用当前接口提供的原请求幂等查询或重试能力，不通过“最近任务”猜测所属任务，不换 ID 自动重发。超过保留窗口无法找回时，应报告结果未知。

## Interrupt and close

1. Confirm whether the user wants the whole command task or one target interrupted.
2. Call `termous.commands.interrupt` once, then poll `termous.commands.get` until the affected target reaches a final state.

停止 AI 会取消该 Run 尚未提交给终端的目标；已经提交的命令继续独立执行。需要停止已执行命令时，仍须使用上述命令任务中断入口。AI 正常完成不会取消已经受理的任务。关闭输出读取、工具超时或 HTTP 断开也不能证明远端命令已结束。
3. For session cleanup, inspect `owned_by_client` and show the exact host and `session_id`. A client with `sessions:close` can close any visible SSH session, including one created in the UI or by another MCP client; disclose that impact before calling `termous.sessions.close`, then re-list sessions to verify removal.
