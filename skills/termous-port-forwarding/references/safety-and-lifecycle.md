# Safety and lifecycle

## Trust and approval

- Termous is authoritative for saved hosts, credentials, SSH transports, forwarding profiles, Core-managed instances, and Host Key decisions.
- Start and stop pass through the shared Termous approval gate. By default, each logical request requires a native decision. A client explicitly configured for approval bypass is automatically approved only within its granted scopes.
- Do not infer bypass from a successful call. Bypass does not grant `forwarding:manage`, broaden host access, or approve Host Keys.
- Approval is bound to the client, `client_request_id`, and normalized request. Reusing an ID with different inputs is an idempotency conflict.
- Approval rejection, expiry, or cancellation means the requested start or stop did not execute. Do not resubmit automatically.
- Once approved execution starts, loss of the MCP response does not imply cancellation. For an immediate response loss, retry only the identical ID and payload; otherwise inspect current instances before deciding on a new request.

## Source and lifecycle boundaries

- `profile_id` uses the saved host and immutable approval-time profile snapshot. It creates `background_profile` and rejects all inline forwarding fields.
- `session_id` creates `session` and reuses that exact connected SSH session. Closing or losing the session stops its session-scoped forwards.
- `host_id` creates `background_once` with a dedicated background SSH transport through the Host's authoritative default SSH Profile. Termous resolves that default to an exact `ssh_profile_id` before approval and idempotency comparison; if the default changes before a retry, reusing the old `client_request_id` can therefore return an idempotency conflict. `ssh_profile_id` creates the same lifecycle through that exact Profile. Neither selector creates or reuses an interactive terminal session, and they are mutually exclusive.
- Profile and one-off background instances are independent of an interactive session, but all instances end when stopped or when Termous Core shuts down.
- Never substitute one source for another to avoid a disconnected session, a changed profile, approval, or Host Key confirmation.

## Global instance model

- Forward instances are Core-global rather than MCP-client-owned. With `forwarding:read`, a client can inspect instances created through the desktop UI or another authorized MCP client.
- With `forwarding:manage` and approval, a client can stop those same instances. Always re-identify the exact global instance and disclose this impact before stopping it.
- Stopping is destructive to the listener and its active connections. It is not restricted to resources created by the caller.
- Saved profiles remain read-only through MCP. Starting a profile does not modify it, and stopping an instance does not delete its profile.

## Network exposure

- Treat every non-loopback bind as a network exposure decision. State which machine hosts the listener and who may reach it.
- `0.0.0.0`, `::`, public interfaces, and remote wildcard binds can expose a service well beyond the initiating client. Never choose them implicitly.
- Dynamic mode is an unauthenticated SOCKS5 proxy. Anyone able to reach the listener can request outbound connections through the SSH path. Default to `127.0.0.1` and require explicit user intent for a broader bind.
- A local forward can expose a remote-side service on the Core machine. A remote forward can expose a Core-side target on the SSH server side. Verify both ends instead of assuming `127.0.0.1` refers to the same host.
- Do not claim that an address is reachable merely because the instance reached `running`; firewalls, server policy, and target availability remain external conditions.

## Host Key handling

- Background profile and one-off starts may need a new or changed Host Key decision.
- MCP exposes only that confirmation is required. It does not expose or authorize the challenge decision.
- Ask the user to inspect the fingerprint and decide in Termous. Never suggest automatic trust, paste a secret, or switch to another SSH mechanism.
- After the native decision, poll the same instance. Do not create a replacement start request merely because it waited for trust.

## Status retention and recovery

- `.instances.list` contains currently managed active or transitional instances, not durable history.
- `.instances.get` can return an active instance and can briefly return a failed instance after it leaves the active list. Failed instances are retained for approximately 30 seconds, then become not found.
- Stopped instances are removed when their terminal transition completes and may become not found immediately after an accepted stop.
- A failed or missing instance does not authorize an automatic restart. Inspect the source, listener conflict, Host Key state, and target details, then ask before creating a new logical request and ID.
- Raw internal failure details and Host Key challenge IDs are intentionally excluded from MCP projections. Do not try to recover them through logs, shell commands, or another interface.

## Reporting checklist

Always report:

- exact requested profile, session, or host source, the runtime `ssh_profile_id` when present, and resulting lifecycle;
- mode and a plain-language network direction;
- requested listener and actual `bound_address` when running;
- target for local and remote modes, or the unauthenticated SOCKS5 warning for dynamic mode;
- approval outcome or bypass only when it was observable;
- `forward_id`, status, phase, and relevant traffic or connection counters;
- Host Key waiting, profile conflicts, failed startup, stop acceptance, and short-lived or missing terminal records without overstating certainty.
