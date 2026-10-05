# Endpoint telemetry safety boundary

GreyGuard Section 13 Part 1 provides governance for optional read-only endpoint telemetry. Every collector is disabled by default and requires a named owner, purpose, consent reference, signed collector fingerprint, exact permission manifest, narrow approved directories, visible monitoring indicator, and retention of no more than 90 days.

Permitted data is limited to approved-process health, filesystem events inside approved directories, network connection metadata without payloads, and resource usage. Command lines, file contents, packet payloads, credentials, cookies, tokens, keystrokes, screens, microphones, and cameras are rejected.

Disabling a collector is immediate and preserves evidence. Uninstall requires explicit confirmation and returns reminders to remove the endpoint component and revoke its credentials. The collector must be removed using the endpoint's managed deployment mechanism; GreyGuard does not install silently or create persistence.
