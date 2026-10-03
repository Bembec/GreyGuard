# Enterprise Session Security

GreyGuard administrator access uses individual local accounts, PBKDF2 password
hashing, role enforcement, login throttling, and final-Platform-Administrator
protection. Production session controls add the following lifecycle.

- Access tokens expire after 15 minutes.
- Refresh tokens expire after seven days and rotate after every use.
- Reusing an old refresh token revokes its entire family and every session for
  the affected administrator.
- Passwords expire after 90 days; a reset restarts the schedule and revokes
  existing sessions.
- TOTP MFA accepts only the current code or one adjacent 30-second window.
- Device name, address, creation, last-seen, expiry, and revocation are retained
  as security evidence.
- Administrators can revoke an individual device; Platform Administrators can
  still revoke every session belonging to an account.

MFA setup secrets are shown only during enrollment and must be stored in an
authenticator application. They must never be logged, copied into source code,
or included in screenshots and support tickets.

Refresh tokens remain in browser session storage, not persistent local storage.
Closing the browser tab removes them. A reuse event fails closed and forces
fresh password and MFA authentication.

Emergency response order: revoke affected sessions, reset the password, replace
the MFA enrollment if exposed, review authentication evidence, and restore
access only after verifying the operator and device.
