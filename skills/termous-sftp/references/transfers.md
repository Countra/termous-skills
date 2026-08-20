# Transfer workflows

## Common preparation

1. Resolve every source and target to an exact MCP-owned `file_session_id`.
2. Refresh each file session with `termous.sftp.sessions.get` immediately before requesting the transfer and retain its current `connection_generation`.
3. For downloads and remote copies, inspect every remote source with `stat`. Upload sources are Core-local paths and are validated by Termous during grant creation and again immediately before execution; do not try to inspect them with an SFTP tool.
4. Choose one explicit overwrite policy:
   - `rename`: preserve existing items by selecting a new target name;
   - `skip`: leave existing targets unchanged and report skipped items;
   - `overwrite`: replace compatible existing files according to Termous transfer semantics.
5. Keep each transfer to 1 through 32 explicitly selected top-level source paths. Do not split a larger request into multiple transfers without a new user decision for each transfer.
6. State the complete transfer direction, paths, target, and overwrite policy. Generate one stable `client_request_id` for that logical transfer.

## Upload local files

Use `termous.sftp.transfers.upload` to copy local files or directories from the machine running Termous Core to one remote file session.

1. Confirm that every local path is absolute and is exactly what the user requested.
2. Explain that these paths refer to the Termous Core machine. Do not silently reinterpret paths from the MCP client's machine.
3. Show all local source paths, the exact remote directory, destination host, and overwrite policy.
4. Call the upload tool. Termous validates the local paths before entering the configured approval gate and revalidates them immediately before transfer execution. Do not try to create or reuse a local grant directly.
5. If approval or task creation is ambiguous, repeat the identical request ID and payload. Never switch to a new request ID automatically.

## Download remote files

Use `termous.sftp.transfers.download` to copy remote files or directories to an existing directory on the machine running Termous Core.

1. Inspect the exact remote source paths and reject symlinks or special files.
2. Confirm the absolute local destination directory with the user.
3. Show every remote source, the Core-local destination, source host, and overwrite policy.
4. Call the download tool. Termous requests native approval unless the client is explicitly configured to skip approvals. When a decision is required, do not treat an MCP-side confirmation as a substitute.
5. Never claim that the local files exist until the transfer task reaches a successful final state.

## Copy between remote hosts

Use `termous.sftp.transfers.remote_copy` to stream files through Termous Core from one remote host to another.

1. Use two connected MCP-owned file sessions whose `host_id` values are different.
2. Pass the source identity as `source_file_session_id` and `source_connection_generation`, and the target identity as `target_file_session_id` and `target_connection_generation`.
3. Use an existing absolute POSIX destination directory as `target_dir`. Show the exact source paths, destination directory, source and target hosts, and overwrite policy.
4. Call the tool once. Termous requests native approval unless the client is explicitly configured to skip approvals. Do not emulate this operation with a local download followed by an upload.
5. Do not describe the operation as server-to-server connectivity: Termous Core relays the bytes.

## Poll and report a task

1. Retain the returned `transfer.id` and pass it as `transfer_id` to `termous.sftp.transfers.get` using the same MCP client.
2. The task is also visible in the Termous Desktop transfer list with an MCP origin marker. The user may cancel or remove it there; another MCP client still cannot inspect or control it.
3. Poll while status is queued or running. Use `phase`, byte counts, file counts, speed, ETA, and current file only as reported.
4. Stop when status is completed, failed, or cancelled. If the owning MCP client receives not found after the task was visible, it may have been removed in Desktop; do not recreate it automatically.
5. Always report:
   - transfer type and source-to-target identity;
   - final status and stable error when present;
   - transferred and total bytes/files when known;
   - skipped item count;
   - `partial=true` and `failure_side` when returned;
   - that completed files are not rolled back after failure or cancellation.

## Cancel a task

1. Confirm the exact task with the user.
2. Call `termous.sftp.transfers.cancel` once.
3. Treat acceptance only as a cancellation request. If `transfers.get` is available, continue polling until the task reaches a final state; otherwise state that final-state inspection requires the separate `sftp:transfer` scope.
4. Never start another transfer automatically after cancellation or failure. MCP-created transfers are intentionally not retryable; a new attempt requires a new user decision and must pass through the configured Termous approval policy.
