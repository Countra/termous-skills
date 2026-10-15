---
name: termous-desktop-workflows
description: Use Termous MCP to create, edit, and run visual RDP/VNC desktop scripts, extract and confirm image templates, and read regression test reports. Use for repeatable desktop workflows, image-based targeting, and UI regression testing. For immediate mouse and keyboard input, use termous-remote-desktop; for local application discovery, use termous-desktop.
---

# Termous Desktop Workflows

Use the authorized `termous.desktop_workflows.*` tools to create, edit, and run repeatable RDP/VNC workflows. The built-in Agent first uses discover_tools to load tools for the intended operation; external MCP clients use their own tool discovery mechanism. A missing tool does not authorize bypassing permissions or reading credentials.

Read the reference relevant to the current task; there is no need to load every reference each time.

For the built-in Agent, the exact tool for creating a fixed-frame snapshot is `termous.desktop_workflows.captures.create(attachment_id)`, which returns `snapshot_id`. Ordinary `termous.desktops.capture` returns only a `screenshot_id` for immediate input; it cannot replace a workflow snapshot, and the identifiers are not interchangeable. Repeated observation does not create a template. Once the image is clear enough, proceed to create or confirm the template, or edit the intended step.

Built-in Agent reference URIs: `skill://termous-desktop-workflows/references/templates.md`, `skill://termous-desktop-workflows/references/editing.md`, and `skill://termous-desktop-workflows/references/runs.md`.

- [Script creation, targeted edits, and versions](references/editing.md)
- [Fixed-frame snapshots, detail views, and template confirmation](references/templates.md)
- [Running a pinned version, reports, and failure handling](references/runs.md)
- For connections and immediate input, see `termous-remote-desktop`.

## Required boundaries

- Use the display-pixel coordinates of the returned image_view. For small targets, inspect a magnified view with captures.view before templates.preview. Core maps coordinates to original pixels; do not calculate the scale manually or invent an original coordinate mode.
- Each template dimension must be 8–512 original pixels. Select compact, stable features, inspect the preview, explicitly confirm it, and only then reference asset_id. Testing the match first is recommended; the test does not click, and a valid template can still be saved when it does not match the current screen.
- Honor any execution budget explicitly supplied for the current Run. When enabled, the budget for the same desktop-selection workflow does not reset after a new capture or a change of request_id. Budgets are disabled by default; do not impose a fixed attempt limit yourself. Use diagnostics to adjust the approach after repeated failures, and tell the user when a required capability or information is missing.
- Image data is delivered only through image content blocks; definitions store asset references only. A model without vision capabilities cannot automatically confirm a visual selection.
- Prefer keyboard shortcuts, text input, and subsequent verification when opening applications or known URLs; do not create a template for every keystroke.
- A fixed screenshot of today's title cannot reliably identify "today's daily report" on future dates. Distinguish a specific issue, the latest issue in a list, and an issue identified by the current date. Explain the limitation when the available pixel-only capabilities are insufficient; do not assume the first item is today's report.
- Run a pinned version. Wait for a terminal state or explicitly cancel before ending the current Run. Never automatically replay input with an uncertain outcome.
- Core still validates permissions, approvals, identities, and ownership for every operation. Closing the page does not affect execution; ending the Agent Run or MCP session cleans up its owned workflow runs.
