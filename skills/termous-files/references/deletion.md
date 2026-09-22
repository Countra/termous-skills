# Deletion workflow

Use the `termous.files.delete.*` tools for deletion. Preview, start, status, and result tools require the separate `files:delete` scope; cancellation requires `files:cancel`. Existing `files:write` access does not include deletion permission. If a tool is missing, direct the user to grant the required scope in Termous rather than bypassing it with shell commands.

WebDAV uses this same workflow. A server-side collection DELETE is recursive, so checking that a directory is empty before deletion cannot eliminate the window for concurrent external additions. Do not claim filesystem-style atomic empty-directory deletion guarantees. Inspect the details after partial failure or an uncertain result; do not replay automatically.

## Preview and start

1. Follow the ordinary file-session workflow to confirm a connected file session owned by the current client. Use the current `file_session_id` and `expected_connection_generation`. An interactive terminal's SSH session ID cannot substitute for a file session ID.
2. Translate the user's request into explicit absolute POSIX `paths` while preserving their meaning. Paths do not expand wildcards or environment variables. Reject the root directory, duplicate paths, and overlapping parent/child paths; do not add neighboring files without authorization.
3. Call `termous.files.delete.preview` with `paths`, `recursive`, the session, and its connection generation. Use `recursive=true` only when deleting non-empty directories is required.
4. Preview scans the complete scope and then returns details in pages. Follow `next_offset` to read the remaining pages and verify that every page has the same `plan_hash`. Never treat the first page as the complete scope. Stop without submitting deletion if scanning fails, a limit is exceeded, or the plan changes.
5. Explain the host, top-level paths, recursive option, actual file/directory/link counts, and that direct deletion cannot be undone. For a symbolic link, delete only the link itself. If a parent path traverses a directory link, ask the user to select the real path explicitly rather than expanding the scope yourself.
6. Keep the same arguments, pass the preview's `plan_hash` as `expected_plan_hash`, and call `termous.files.delete.start` with one stable `client_request_id`. Termous uses native approval by default. Explicit approval bypass still enforces permission and plan revalidation; do not infer or change that setting.
7. Retain the returned task ID. Approval or task creation means only that execution may begin, not that deletion has completed.

Preview limits are 500 top-level paths, 10,000 manifest nodes, 256 levels, and a 4 MiB plan payload. Preview and pre-execution revalidation each have a 30-second timeout. Report exceeded limits and ask the user to narrow the scope; do not automatically split the request into multiple mutations to bypass them.

## Inspect results and cancel

- Poll owned tasks through `termous.files.delete.get` until `completed`, `failed`, or `cancelled`.
- Read final results in pages through `termous.files.delete.result`. Report counts for `deleted`, `failed`, `not_executed`, and `uncertain`, along with relevant paths. Never omit `partial` or `uncertain` outcomes.
- Calling `termous.files.delete.cancel` only requests that subsequent steps stop. `cancel_requested=true` does not mean the task has ended or content has been restored. Continue querying the final state before reporting the actual result.
- If the current client has `files:cancel` but not `files:delete`, it cannot call the status or result tools after cancellation. Report only that cancellation was requested and explain that inspecting the final result requires `files:delete`; do not infer what was deleted.
- Explicitly stopping the AI assistant cancels deletions initiated by that run/generation, but does not restore completed deletions. Normal response completion differs from an explicit stop; do not rely on ending the response to cancel a task.
- Directory contents added during deletion are not automatically included in the scope. Report a conflict if a directory is no longer empty or a source has changed; do not append another recursive deletion pass.

## Failure and retry boundaries

- A rejected, expired, or cancelled pending approval does not authorize execution; do not automatically request approval again.
- If the start response is immediately lost, recover the existing request only with the original request ID and identical arguments. Do not automatically retry under a different ID.
- A changed plan requires a new preview and confirmation; never attach a new plan to an old request ID.
- A network interruption may occur after remote deletion but before its response arrives. On `uncertain`, stop automatic writes and inspect the affected paths; do not claim that nothing executed.
- Request idempotency and task history are bounded in-memory records. Do not automatically replay after Core restarts. Read the current file state, preview the scope again, and obtain fresh authorization for the operation.
- Multi-path deletion operations are not atomic transactions. Neither cancellation nor failure guarantees rollback.
