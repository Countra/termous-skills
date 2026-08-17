# Tool workflows

## Saved host discovery

1. Call `termous.hosts.list` without assuming that an old host ID still exists.
2. Filter using user-provided names, tags, endpoints, or platform hints.
3. Treat `unknown`, `checking`, `online`, `offline`, and `unavailable` as cached ICMP reachability only.
4. Call `termous.hosts.refresh_reachability` only when the user needs a fresh network hint and the client has `hosts:probe`.
5. If matching remains ambiguous, present short host summaries and ask the user to select one.

## Start or reuse an SSH session

1. Call `termous.sessions.list` and match by exact `host_id`.
2. Reuse a session only when `status` is `connected` and `phase` is `ready`, unless the user requested a new one.
3. To create one, generate one stable `client_request_id` for the logical attempt and call `termous.sessions.connect`.
4. Use the returned `session.id` as `session_id` and poll `termous.sessions.get`.
5. Handle states explicitly:
   - `status=connected` and `phase=ready`: continue;
   - `status=connecting` or a pre-ready phase: wait and poll;
   - `status=waiting_host_trust` or `host_key_confirmation_required=true`: ask the user to act in Termous;
   - `status=failed` or `status=disconnected`: report the stable error and stop or ask before retrying.
6. If the connect response is immediately lost, retry the identical payload with the same caller-generated `client_request_id`. Generate one ID per logical attempt; keep it valid UTF-8, non-empty, and no longer than 128 bytes.
7. Treat connect idempotency as a bounded in-memory recovery window, not a persistent key. After a longer interruption or Core restart, call `termous.sessions.list` before deciding whether to create another session.
8. If `termous.sessions.get` is unavailable, do not claim that the returned session became ready. Ask the user to grant `sessions:read` or inspect the session in Termous.

## Dispatch an approved command

1. Freeze the ordered list of exact SSH `session_id` values.
2. Reject multiline input locally. Do not rewrite, wrap, escape, or append shell syntax to the command.
3. Confirm that `termous.commands.get` and `termous.commands.read_output` are available before execution. If not, explain that `commands:read` is required to verify results.
4. Tell the user the complete command and targets, then call `termous.commands.dispatch` with a stable `client_request_id`.
5. The call waits for native Termous approval. Do not substitute an MCP-side confirmation.
6. Interpret outcomes:
   - approval rejected/expired/cancelled: nothing was sent;
   - task busy: the approval is not queued; ask before creating another request;
   - task returned: retain its `task_id` and continue polling.
7. If the HTTP result is ambiguous, retry the identical payload with the identical `client_request_id`.

## Poll status and read output

1. Call `termous.commands.get` using the owning client and `task_id`.
2. For each target, call `termous.commands.read_output` with its `session_id`.
3. Start without an epoch and with offset `"0"`, unless a previous response supplied a cursor.
4. Preserve `epoch` exactly and pass `next_offset` as a decimal string on the next call.
5. Inspect the returned `encoding`. Read `utf8` data directly and decode `base64` data as bytes; the tool selects the safe encoding automatically.
6. Stop reading only when `eof` is true. A completed task and a fully consumed output stream are related but distinct states.
7. If a gap is reported, state its code and the returned offsets. Report a missing byte interval only when it can be derived safely; `epoch_mismatch` and `offset_ahead` do not prove such an interval. Do not present concatenated text as complete.
8. Report `truncated` even when the visible tail looks sufficient.

## Interrupt a command

1. Confirm that the user wants to interrupt the whole task or a specific target.
2. Call `termous.commands.interrupt` with `task_id` and, for one target, its exact `target_session_id`.
3. Treat `accepted: true` only as acknowledgement of the intent.
4. Poll `termous.commands.get` until each affected target reaches a final state. If that tool is unavailable, say that final interruption cannot be verified. Termous owns trusted prompt recovery and input-lock release.

## Close a session

1. Show the exact session and host before closing an existing session.
2. Call `termous.sessions.close` only with explicit user intent or for clearly requested cleanup.
3. A client with `sessions:close` may close any SSH session visible to Termous, including one opened in the UI; do not assume ownership protection.
4. Re-list sessions to confirm the result.
