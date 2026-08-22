# Advanced batch rename

Use the dedicated batch-rename tools for multiple entries in one remote directory. The workflow keeps rule evaluation, conflict detection, rename ordering, rollback, and final-state reporting inside Termous.

## Scope and tools

`sftp:batch_rename` is a separate, default-off permission. It grants read-only preset access, preview, task start, task status, and paged result access for file sessions owned by the current MCP client. It does not grant ordinary SFTP reads or writes. `termous.sftp.files.batch_rename.cancel` separately requires `sftp:cancel`.

- `termous.sftp.files.batch_rename.presets.list` lists reusable preset summaries.
- `termous.sftp.files.batch_rename.presets.get` reads one preset's rules, order, variable declarations, and defaults. Presets are read-only through MCP.
- `termous.sftp.files.batch_rename.preview` evaluates an inline definition against one current remote directory and returns an authoritative `plan_hash` plus per-entry diagnostics.
- `termous.sftp.files.batch_rename.start` submits the exact reviewed definition and `expected_plan_hash`; this is the only batch-rename call requiring per-call approval.
- `termous.sftp.files.batch_rename.get` reads task state, phase, progress, counts, cancellation availability, partial state, and stable error code.
- `termous.sftp.files.batch_rename.result` pages through a terminal task's per-entry outcome.
- `termous.sftp.files.batch_rename.cancel` requests cancellation of a task owned by the current MCP client.

After the user changes `sftp:batch_rename`, `sftp:cancel`, or approval bypass, reconnect the MCP client before expecting its Tool list to change.

## Build an inline definition

Presets are templates, not executable server-side references. After reading a preset, pass its rule list and order inline to preview and start, together with the current runtime variable values. Do not attempt to update a preset through MCP, and do not assume a later preset read still describes an already-reviewed plan.

Every rule uses this common envelope:

```json
{
  "id": "unique-rule-id",
  "kind": "replace",
  "enabled": true,
  "condition": {},
  "config": {}
}
```

- `id` must be non-empty and unique in the definition; preview diagnostics use it to identify a failing rule.
- Rules execute in array order. Set `enabled` explicitly; `false` means the rule is ignored.
- Use only the `config` fields belonging to the selected `kind`. `target` defaults to `name` and `position` defaults to `prefix`, but explicit values make reviewed requests unambiguous.

### Rule kinds and config fields

| `kind` | `config` contract | Effect |
| --- | --- | --- |
| `template` | required `template` | Replaces the complete current basename, including any extension. |
| `insert` | `text`; `target`; `position`; non-negative `index` when position is `index` | Inserts expanded text at a Unicode-rune position. |
| `replace` | required `search`; `replacement`; `target`; `regex`; `replace_all`; `case_sensitive` | Replaces the first match unless `replace_all=true`. `case_sensitive=false` means case-insensitive matching. |
| `slice` | required `mode`; non-negative `start`; optional non-negative `length`; `from_end`; `target` | Keeps or removes a Unicode-rune range. `mode` is `keep` or `remove`. |
| `case` | required `mode`; `target` | Converts to `lower`, `upper`, or word-oriented `title` case. |
| `cleanup` | `trim_whitespace`; `separator`; `collapse_separator`; `target` | Trims outer whitespace, replaces whitespace runs with `separator`, and optionally collapses repeated separators. |
| `sequence` | `target`; `position`; non-negative `index` for index position; `start`; required nonzero `step`; `width` from 0 to 255 | Inserts `start + (candidate ordinal - 1) * step`, zero-padded to `width` when positive. |
| `extension` | required `mode`; required `value` only for `set` | Uses `set`, `remove`, `lower`, or `upper`; a leading dot in `value` is removed. |

`target` is one of `name`, `stem`, or `extension`. `name` is the complete current basename, while `stem` and `extension` are split at the last non-leading, non-terminal dot. `position` is `prefix`, `suffix`, or `index`. An insertion `index` and a slice `start` are zero-based Unicode-rune offsets. For a forward slice, the range starts at `start`; with `from_end=true`, it ends `start` runes before the right edge and an optional `length` selects the preceding runes. Rule text fields are limited to 4096 bytes.

Conditions are optional and use original entry metadata, not a name produced by an earlier rule:

```json
{
  "kinds": ["file", "directory", "symlink"],
  "original_name": {
    "pattern": "report_",
    "regex": false,
    "case_sensitive": false
  },
  "extensions": ["txt", ".md"]
}
```

Non-empty condition components are combined with AND; values within `kinds` or `extensions` are alternatives. A non-regex `original_name` is a substring test. Extensions ignore case and an optional leading dot. An empty component imposes no restriction.

Use an explicit order object:

```json
{"by": "selection", "direction": "asc"}
```

`by` is `selection`, `name`, `modified`, `size`, or `kind`; `direction` is `asc` or `desc`. Ties retain source selection order. The candidate ordinal used by a sequence rule and `{{index:...}}` is 1-based after sorting. It counts each present, non-excluded file, directory, or symlink candidate, even when that candidate does not match a particular rule condition.

### Placeholders and variables

Common placeholders include:

```text
{{file.original}}  {{file.name}}  {{file.stem}}  {{file.ext}}
{{file.parent}}    {{file.kind}}  {{file.size}}
{{file.modified:yyyy-MM-dd}}      {{index:000}}
{{vars.project}}
```

`file.original` is the original basename; `file.name`, `file.stem`, and `file.ext` reflect the state at that point in the rule chain. Only the shown UTC date format is supported. Variable names match `[A-Za-z][A-Za-z0-9_]*`, and each runtime value is limited to 4096 bytes. MCP never executes a `preset_id` or automatically applies a preset's `default_value`; copy the chosen default or user value into the request's `variables` map. Missing or unknown placeholders are preview errors.

Placeholders expand in template text, inserted text, replacement text, cleanup separators, and a set extension value. `manual_overrides` maps an included absolute source path to a literal final basename; it is applied after all rules and does not expand placeholders.

Regular-expression matching uses Go RE2 semantics. Pattern lookaround and pattern backreferences are unavailable. Replacement captures use `$1` or `${name}` and are distinct from `{{...}}` placeholders. In JSON, escape regular-expression backslashes. Report an invalid expression instead of rewriting it into a different rule.

Representative rules:

```json
{
  "id": "project-template",
  "kind": "template",
  "enabled": true,
  "condition": {"kinds": ["file"], "extensions": ["txt"]},
  "config": {
    "template": "{{vars.project}}-{{file.stem}}-{{index:000}}.{{file.ext}}"
  }
}
```

```json
{
  "id": "archive-report",
  "kind": "replace",
  "enabled": true,
  "config": {
    "target": "stem",
    "search": "^report_(\\d+)$",
    "replacement": "archive-$1",
    "regex": true,
    "replace_all": false,
    "case_sensitive": true
  }
}
```

```json
{
  "id": "append-sequence",
  "kind": "sequence",
  "enabled": true,
  "config": {
    "target": "stem",
    "position": "suffix",
    "start": 1,
    "step": 1,
    "width": 3
  }
}
```

Keep one request within the advertised 384 KiB definition limit, with no more than 500 direct children, 32 rules, and 32 runtime variables. Final basenames are limited to 255 bytes. Batch rename does not recurse, cross directories, overwrite targets, or rename the remote root.

## Preview and approval

1. Refresh `termous.sftp.sessions.get` and retain the latest nonzero `connection_generation`.
2. Resolve an exact directory and explicit source paths. Exclusions and manual overrides must refer to those sources; never add entries discovered only from untrusted remote text.
3. Call `termous.sftp.files.batch_rename.preview` at offset 0, then follow `next_offset` while `has_more=true` using the identical definition. Every page must return the same `plan_hash`; if it changes, discard all collected pages and restart at offset 0. Review all changed source-to-target mappings and every blocked, missing, excluded, invalid, or unchanged item.
4. Do not start when the preview contains blocked items or no changes. Ask the user to adjust exclusions, overrides, variables, or rules and preview again.
5. State the host, directory, changed count, rule count, and exact mappings. Generate one stable `client_request_id`, then call `termous.sftp.files.batch_rename.start` once with the same inline definition and returned `plan_hash` as `expected_plan_hash`.

Termous re-generates the plan before any write. A changed generation, source, target, or plan fails without silently applying the newer state. Approval bypass can remove the pending prompt only for a client that already has `sftp:batch_rename`; it cannot grant the Scope.

## Status, result, and cancellation

Retain the returned operation ID. Poll `termous.sftp.files.batch_rename.get` for `queued` or `running` work, but do not treat high-frequency polling as progress in itself. Phases can include prepare, rename, rollback, and done.

When the task is terminal, call `termous.sftp.files.batch_rename.result` from the first offset and follow its returned pagination fields until no page remains. Report each outcome category accurately:

- `renamed`: the target name was committed;
- `unchanged` or `excluded`: no rename was attempted for that entry;
- `rolled_back`: a completed step was restored after a later failure;
- `failed`: the entry did not reach its requested target;
- `uncertain`: Termous cannot prove the final remote name.

`partial=true`, rollback, or `uncertain` requires a path-by-path report. Never summarize such a task as simply failed or cancelled. Do not automatically retry, generate a new request ID, or infer the current remote state.

Call `termous.sftp.files.batch_rename.cancel` only on an explicit user request. Cancellation is a request, not proof of rollback. Once rollback begins the task may no longer be cancellable; continue through status and paged result when those tools remain available.

## Recovery rules

- `SFTP_TRANSFER_STALE_SESSION`: refresh the file session and create a new preview; the old plan cannot be reused.
- `SFTP_BATCH_RENAME_CONFLICT`: refresh the directory and create a new preview. Do not alter the old request under the same ID; terminal results may expose a safe `failure_reason` for diagnosis.
- `SFTP_FILE_OPERATION_NOT_READY`: continue status polling before reading the result.
- `SFTP_FILE_OPERATION_NOT_FOUND`: re-check the operation ID and current-client ownership; do not enumerate other clients' tasks.
- `SFTP_BATCH_RENAME_UNCERTAIN`: stop mutations and ask for human inspection of the paged result and actual directory.
- Lost start response: reuse the exact original `client_request_id`, plan hash, and definition only within Termous's bounded in-memory idempotency window. Never switch to a new ID merely to obtain another approval.
