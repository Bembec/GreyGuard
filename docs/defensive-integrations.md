# Browser connectors and defensive response

GreyGuard Section 13 Part 2 adds optional per-site browser connectors and reversible defensive-response plans. Both remain disabled or pending until explicitly authorized.

Browser connectors require a named owner, purpose, consent reference, visible indicator, and exact domain allowlist. They reject password fields, cookies, session tokens, authorization data, and domains outside the allowlist. Administrators can disconnect them immediately.

Defensive actions are limited to approved-process termination, recoverable file quarantine, temporary network isolation, credential revocation, agent suspension, and tool or integration disablement. Requests preserve evidence, expire within 24 hours, require a separate approver, and declare recovery to the previous state. Execution requires a controlled adapter; approval alone never runs an arbitrary host command.

Hack-back, exploitation, flooding, destructive external action, credential theft, covert monitoring, and irreversible retaliation are not allowlisted.
