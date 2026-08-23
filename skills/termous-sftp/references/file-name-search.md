# Linux file-name search

Use this workflow only for file-name search through a ready, current-client Termous SFTP file session. It uses the remote host's compatible `fd` or `fdfind` executable through Termous; it is not a content search and it does not create a separate SSH connection.

## Required capability check

1. Obtain the latest `file_session_id` and nonzero `connection_generation` from `termous.sftp.sessions.get`.
2. Call `termous.sftp.files.name_search.capability` with that generation before every logical search workflow.
3. Continue to `termous.sftp.files.name_search.run` only when `status=ready`.

Handle every capability status explicitly:

- `ready`: retain the returned generation and continue.
- `missing`: stop. Tell the user that compatible `fd` is not installed and that they can install it manually or use the installation entry in the Termous file manager.
- `outdated`: stop. Report the detected version and `minimum_version`, then direct the user to upgrade manually or through Termous.
- `unsupported`: stop. Report the returned safe message; do not infer an installation procedure.

The MCP capability result deliberately contains no package manager, privilege, install plan, or command. There is no MCP installation Tool. Never call `commands.dispatch` to install or upgrade `fd`, and never fall back to `find`, `locate`, or an ad hoc Shell invocation. Host Key trust must still be resolved in Termous.

Capability and search are read-only and do not use `client_request_id` or per-call approval. They still require the dedicated `sftp:file_search` Scope; approval bypass neither grants that Scope nor makes another client's file session visible.

## Search request

Call `termous.sftp.files.name_search.run` with the same `file_session_id` and latest `expected_connection_generation`. The Tool rechecks capability immediately before searching, so a prior `ready` result does not override a later unavailable state.

Choose filters deliberately:

| Field | Values and behavior |
| --- | --- |
| `query` | Required single-line UTF-8 expression, at most 255 bytes. Its meaning follows `match_mode`. |
| `search_root` | Absolute Linux path, default `/`, at most 4096 bytes. `/proc`, `/sys`, `/dev`, `/run`, and their descendants cannot be selected as the root. |
| `entry_type` | `all` by default, or `file` / `directory`. Size filters require `file`. |
| `match_mode` | `literal` by default, or `regex` / `glob`. Regex uses the remote compatible `fd` engine; do not assume unsupported look-around or backreferences. |
| `case_mode` | `insensitive` by default, or `smart` / `sensitive`. Smart mode becomes case-sensitive when the query contains an uppercase character. |
| `match_target` | `name` by default, or `full_path`. A name-target query cannot contain `/`. |
| `hidden_mode` | `include` by default; use `exclude` to omit hidden entries. |
| `ignore_mode` | `bypass` by default; use `respect` to honor remote ignore files and patterns. |
| `one_file_system` | `false` by default, so real mounted filesystems may be searched. Set `true` to stay on the root's filesystem. |
| `max_depth` | `0` means unlimited; otherwise use `1` through `256`. |
| `extensions` | Up to 16 extensions, combined as alternatives. A leading dot is optional; after normalization each value must be nonempty, at most 64 UTF-8 bytes, and contain no NUL, path separator, or line break. |
| `exclude_globs` | Up to 16 nonempty `fd` exclusion globs, each at most 255 UTF-8 bytes with no NUL or line break. These filter results independently from `match_mode`. |
| `modified_after`, `modified_before` | Optional RFC3339 timestamps. When both are present, `modified_after` must be earlier. |
| `min_size_bytes`, `max_size_bytes` | Optional inclusive, nonnegative bounds with minimum no greater than maximum; valid only for `entry_type=file`. |
| `limit` | Omit it or use `0` for the default 100; explicit result limits must be from 1 through 200 for MCP. |

Examples of intentional filter combinations:

- Find case-insensitive basename substrings: `match_mode=literal`, `case_mode=insensitive`, `match_target=name`.
- Match an expression across the complete path: `match_mode=regex`, `match_target=full_path`.
- Limit a broad search to files: `entry_type=file`, selected `extensions`, and size or modification-time bounds.
- Respect a repository's ignore policy: `ignore_mode=respect`; do not assume this is the default.

Search never follows directory symlinks. A root search always excludes the protected Linux pseudo-filesystems. The operation has a bounded runtime and shares a per-host execution slot with Termous file search and dependency installation, so another active operation may return a busy error.

## Interpret results

Each item contains only `path`, `name`, and `parent_path`. Results are stably ordered by case-folded name and then path. There is no pagination or total count.

- `returned_count`: number of complete items actually returned.
- `truncated=true`: the result limit or MCP response budget was reached. Refine the root or filters instead of claiming the list is complete.
- `partial=true`: `fd` reported inaccessible entries or other warnings, so the result may be incomplete. The underlying stderr is not exposed; returned paths remain usable, but report the partial state.
- `timed_out=true`: the scan reached its time limit and the returned items are partial.
- `skipped_invalid_utf8`: count of remote paths omitted because they could not be represented safely.
- `connection_generation`: generation used by the search; do not reuse results as authority after that generation changes.
- `one_file_system`: confirms whether mount-boundary restriction was applied.

The MCP projection has a 256 KiB structured-result budget. It preserves a complete, stable prefix and sets `truncated=true` rather than cutting a UTF-8 path. Absolute paths can reveal sensitive host layout; return only the paths relevant to the user's requested search.

## Recovery

- Missing `sftp:file_search`: ask the user to grant that exact Scope and reconnect the MCP client. `sftp:read` does not imply whole-host name search.
- Stale generation or missing file session: re-list current-client SFTP sessions and repeat capability detection with the new generation. Do not substitute an interactive SSH session ID.
- `SFTP_FILE_SEARCH_UNAVAILABLE`: stop and run capability again. If it is non-ready, direct the user to manual or Termous installation; do not install through MCP.
- `SFTP_FILE_SEARCH_BUSY`: wait for the existing host operation to finish, then ask before rerunning a broad scan.
- `SFTP_FILE_SEARCH_TIMEOUT`: narrow the root or filters before retrying; do not claim a complete result.
- `SFTP_FILE_SEARCH_FAILED`: report the stable error and stop. Do not switch to another search implementation.
