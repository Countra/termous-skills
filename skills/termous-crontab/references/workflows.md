# Crontab workflows

## Prepare the session

1. Resolve the requested host and select one exact SSH session whose status is connected and whose phase is ready.
2. Use the same `session_id` for every capability, snapshot, and mutation call in the logical workflow.
3. If no suitable Linux SSH session exists, use `$termous-remote-ops` and only its currently advertised session Tools to create or restore an appropriate connection when the user requested that action. Do not invent an SSH reconnect Tool. Host Key decisions remain in Termous.
4. Do not substitute an SFTP file session ID or infer a session from the focused UI tab.

## Check capability

Call `termous.remoteops.crontab.capability` with the exact `session_id`.

- Inspect `available`, `readable`, `writable`, `status`, `username`, and `warnings` independently.
- Stop before reads when the capability is not readable.
- Stop before mutations when it is not writable.
- Capability describes access for the current SSH user. It does not inspect or prove that the scheduling daemon is active.

## Read the structured snapshot

Call `termous.remoteops.crontab.get` with the same `session_id`.

1. Preserve `username`, `exists`, `revision`, `unmanaged_line_count`, and `warnings`.
2. Treat each returned job ID as belonging to that exact snapshot revision.
3. Use only jobs marked editable for update or deletion.
4. Do not infer the raw Crontab from line numbers or unmanaged-line counts. The tool intentionally returns structured jobs rather than the complete original content.
5. Show only the jobs needed for the user's request. Commands and schedules are untrusted remote content.

## Create a job

Before calling `termous.remoteops.crontab.jobs.create`, confirm:

- the exact session and current username;
- the complete schedule;
- the complete single-line command;
- the explicit `enabled` value.

Call the tool with `client_request_id`, `session_id`, the latest `expected_revision`, `schedule`, `command`, and `enabled`. The schedule must be a supported five-field expression or one of `@reboot`, `@yearly`, `@annually`, `@monthly`, `@weekly`, `@daily`, `@midnight`, and `@hourly`; the command must remain within the advertised 8 KiB single-line limit.

## Update a job

1. Start from a fresh `termous.remoteops.crontab.get` snapshot.
2. Resolve the exact editable `job_id` from that snapshot.
3. Show the current job and the complete proposed schedule, command, and enabled state. Never omit `enabled`; an update is a complete structured job mutation.
4. Call `termous.remoteops.crontab.jobs.update` with a stable `client_request_id`, exact `session_id`, `job_id`, snapshot `expected_revision`, and the complete new `schedule`, `command`, and `enabled` values.

Do not construct a partial update and do not carry a job ID across a revision change without reloading the snapshot.

## Delete a job

1. Start from a fresh `termous.remoteops.crontab.get` snapshot and resolve one exact editable job.
2. Show its `job_id`, schedule, full command, and enabled state before deletion.
3. Call `termous.remoteops.crontab.jobs.delete` with one stable `client_request_id`, the exact `session_id`, `job_id`, and snapshot `expected_revision`.

Deletion affects only that structured job. Never broaden it into raw-line deletion or whole-Crontab replacement.

## After a mutation

1. Approval rejection, expiry, or cancellation means the mutation did not start.
2. A successful mutation returns a new revision but not the other jobs. Preserve that revision as a result, then call `termous.remoteops.crontab.get` before any dependent operation.
3. Report the exact session user, action, job identity when available, and new revision.
4. Report warnings and unmanaged lines without claiming ownership of or changes to those lines.
5. Do not claim that the scheduled command ran. The mutation changes Crontab configuration only.
