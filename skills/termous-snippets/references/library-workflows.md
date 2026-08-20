# Snippet library workflows

## Read groups and snippets

1. Call `termous.snippets.groups.list` to inspect group IDs and ordering. This Tool has no pagination; if it returns `truncated=true`, the complete group snapshot is unavailable through MCP and group reorder must stop. Use `termous.snippets.groups.get` for one current group and its `updated_at` value.
2. Call `termous.snippets.list` with a narrow query, group, shell, favorite filter, offset, and bounded limit when appropriate.
3. Continue snippet pagination with the next offset while its result reports `truncated=true`. A summary list never contains the full command.
4. Call `termous.snippets.get` using one exact snippet ID before editing or executing it.

## Create and update groups

- Use `termous.snippets.groups.create` with a stable `client_request_id`, the confirmed name, and an optional sort order.
- Before `termous.snippets.groups.update`, reload the exact group and pass its `updated_at` as `expected_updated_at` with the complete intended name and sort order.
- Before `termous.snippets.groups.delete`, show that deleting the group leaves its snippets intact and ungrouped, then pass the latest `expected_updated_at`.
- `termous.snippets.groups.reorder` requires a complete, non-truncated current group snapshot. Include every group exactly once with a unique sort order and its own latest `expected_updated_at`; never submit a filtered, truncated, or stale subset.

## Create and update snippets

- Use `termous.snippets.create` only after confirming the full name, optional group, description, tags, shell, favorite state, and command.
- Before `termous.snippets.update`, call `termous.snippets.get`, preserve the latest `updated_at`, and submit the complete intended snippet rather than an assumed partial patch.
- Before `termous.snippets.delete`, show the exact snippet and full command when available, then pass its latest `expected_updated_at`.
- All seven write Tools use one stable `client_request_id` per logical operation and the native Termous approval policy.
