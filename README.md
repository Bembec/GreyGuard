<p align="center">
  <img src="assets/greyguard-symbol.png" alt="GreyGuard official symbol" width="180">
</p>

# GreyGuard

GreyGuard is a defensive AI-agent identity, permission, risk, and security control plane written in Python.

It authenticates agents before accepting requests, enforces agent-specific scope boundaries, evaluates actions using `ALLOW`, `ASK`, or `BLOCK` policies, tracks risk independently, suspends unsafe agents, and stores audit evidence.

> **Core security principle:** Agent identity is not the same as agent permission.

## Current Version

**Version 9 — Agent Identity and Scope Boundary Enforcement**

GreyGuard now follows this security flow:

```text
Agent credential
→ Identity authentication
→ Scope boundary enforcement
→ Permission policy
→ Risk update
→ Audit evidence
```

## Core Features

* Multi-agent registration and independent state
* Unique agent credentials
* Salted PBKDF2 credential hashing
* Constant-time credential comparison
* Agent-specific action scopes
* Credential rotation
* Credential revocation
* Identity-impersonation prevention
* HTTP `401` authentication failures
* HTTP `403` scope failures
* `ALLOW`, `ASK`, `BLOCK`, and `REFUSED` decisions
* Human approval and denial
* Weighted risk scoring
* Automatic suspension
* Administrator-controlled reset
* JSON state persistence
* SQLite audit history
* Authentication-event evidence
* FastAPI REST endpoints
* Interactive OpenAPI documentation

## Project Structure

```text
GreyGuard/
├── api.py
├── database.py
├── main.py
├── requirements.txt
├── README.md
└── .gitignore
```

The following runtime files are generated locally and excluded from Git:

```text
greyguard_state.json
greyguard.db
greyguard_greyguard_greyguard_security.log
__pycache__/
```

## Security Layers

GreyGuard evaluates requests through three separate controls.

### 1. Authentication

Authentication answers:

```text
Who is making this request?
```

An agent supplies:

```text
X-Agent-Name
X-Agent-Key
```

GreyGuard verifies the credential against its stored salted hash.

### 2. Scope Authorization

Authorization answers:

```text
Is this authenticated agent permitted to request this action?
```

A valid credential does not grant every permission. The requested action must appear in that agent's scopes.

### 3. Security Policy

Policy evaluation answers:

```text
What security decision applies to this permitted request?
```

Even when an agent is authenticated and has the correct scope, GreyGuard may still return `ASK` or `BLOCK`.

Example:

```text
Identity authenticated
→ send_email scope allowed
→ security policy returns BLOCK
→ risk score increases
```

## Permission Policy

| Action          | Policy  | Risk |
| --------------- | ------- | ---: |
| `read_file`     | `ALLOW` |    0 |
| `search_logs`   | `ALLOW` |    0 |
| `delete_file`   | `ASK`   |   20 |
| `run_program`   | `ASK`   |   25 |
| `send_email`    | `BLOCK` |   40 |
| `view_audit`    | `ALLOW` |    0 |
| `audit_summary` | `ALLOW` |    0 |
| Unknown action  | `BLOCK` |   50 |

## Risk Levels

|         Score | Risk level |
| ------------: | ---------- |
|          0–19 | `LOW`      |
|         20–59 | `MEDIUM`   |
|         60–99 | `HIGH`     |
| 100 or higher | `CRITICAL` |

An agent is suspended when it reaches:

* Three blocked attempts, or
* A risk score of 100

Suspended agents receive `REFUSED`, even when requesting an ordinarily allowed action.

## Installation

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

Check the Python files:

```powershell
python -m py_compile main.py database.py api.py
```

## Terminal Mode

Run the local terminal interface:

```powershell
python main.py
```

Terminal commands include:

```text
list_agents
switch_agent
reset
quit
```

Supported demonstration actions include:

```text
read_file
search_logs
delete_file
run_program
send_email
view_audit
audit_summary
```

The terminal interface remains available for local development and recovery. V9 credential and scope enforcement protects FastAPI agent requests.

## FastAPI Mode

Set an administrator PIN for the current PowerShell session:

```powershell
$env:GREYGUARD_ADMIN_PIN = "choose-a-private-pin"
```

Start the API:

```powershell
python -m uvicorn api:app --reload
```

Open the interactive documentation:

```text
http://127.0.0.1:8000/docs
```

Stop the server with `Ctrl + C`.

Do not commit the administrator PIN or place a real PIN in the README.

## Agent Credentials

Agent credentials begin with:

```text
gg_
```

The original credential is displayed only when:

* An identity is created
* A credential is rotated

GreyGuard stores only:

* A random salt
* A PBKDF2-derived hash

It does not store the original credential. If a credential is lost, rotate it.

Never commit agent credentials to Git, place them in source code, paste them into documentation, or expose them in logs.

## API Request Headers

Administrative endpoints use:

```text
X-Admin-Pin
```

Agent endpoints use:

```text
X-Agent-Name
X-Agent-Key
```

## API Endpoints

| Method | Endpoint                                     | Protection | Purpose                                |
| ------ | -------------------------------------------- | ---------- | -------------------------------------- |
| `GET`  | `/`                                          | Public     | Application information                |
| `GET`  | `/health`                                    | Public     | Health and registration counts         |
| `GET`  | `/permissions`                               | Public     | Policy and available scopes            |
| `GET`  | `/agents`                                    | Admin      | List registered agents                 |
| `POST` | `/agents`                                    | Admin      | Register identity and issue credential |
| `GET`  | `/agents/{agent_name}`                       | Admin      | View an agent                          |
| `PUT`  | `/agents/{agent_name}/scopes`                | Admin      | Replace assigned scopes                |
| `POST` | `/agents/{agent_name}/credential/rotate`     | Admin      | Rotate credential                      |
| `POST` | `/agents/{agent_name}/credential/revoke`     | Admin      | Revoke credential                      |
| `POST` | `/actions/evaluate`                          | Agent      | Authenticate, authorize, and evaluate  |
| `GET`  | `/agents/{agent_name}/audit`                 | Agent      | View own audit events                  |
| `GET`  | `/agents/{agent_name}/summary`               | Agent      | View own audit summary                 |
| `GET`  | `/agents/{agent_name}/authentication-events` | Admin      | View identity-security evidence        |
| `POST` | `/agents/{agent_name}/reset`                 | Admin      | Reset suspended agent                  |

## Registering an Identity

Use `POST /agents` with the administrator PIN.

Example body:

```json
{
  "agent_name": "research_agent",
  "scopes": [
    "read_file",
    "search_logs",
    "view_audit",
    "audit_summary"
  ]
}
```

The response contains a credential once:

```json
{
  "agent_name": "research_agent",
  "credential": "gg_REDACTED",
  "credential_notice": "Save this credential now. GreyGuard will not display it again."
}
```

`gg_REDACTED` is documentation text, not a working credential.

## Evaluating an Action

Use `POST /actions/evaluate`.

Headers:

```text
X-Agent-Name: research_agent
X-Agent-Key: the privately stored agent credential
```

Request body:

```json
{
  "action": "read_file",
  "approval": null
}
```

Example successful response:

```json
{
  "identity_authenticated": true,
  "scope_authorized": true,
  "agent_name": "research_agent",
  "action": "read_file",
  "policy_decision": "ALLOW",
  "approval": "NOT_REQUIRED",
  "risk_added": 0,
  "risk_score": 0,
  "risk_level": "LOW",
  "blocked_attempts": 0,
  "agent_status": "ACTIVE",
  "message": "Action allowed by policy."
}
```

## Authentication and Authorization Results

| Situation                              | HTTP status | Meaning                           |
| -------------------------------------- | ----------: | --------------------------------- |
| Valid credential and valid scope       |       `200` | Request reaches the policy engine |
| Missing or invalid credential          |       `401` | Identity was not authenticated    |
| Revoked credential                     |       `401` | Identity authentication failed    |
| Valid credential but missing scope     |       `403` | Identity lacks permission         |
| Agent attempts another agent's records |       `403` | Resource boundary denied          |
| Unknown administrative resource        |       `404` | Requested record was not found    |

## Human Approval

Actions with an `ASK` policy support:

```text
APPROVED
DENIED
PENDING
```

Example:

```json
{
  "action": "delete_file",
  "approval": "APPROVED"
}
```

An `ASK` request without an approval value returns `PENDING`.

## Credential Rotation

Credential rotation:

* Generates a new credential
* Invalidates the old credential immediately
* Reactivates a previously revoked identity
* Displays the new credential only once
* Records the rotation timestamp

Use:

```text
POST /agents/{agent_name}/credential/rotate
```

## Credential Revocation

Revocation prevents the current credential from authenticating.

Use:

```text
POST /agents/{agent_name}/credential/revoke
```

A revoked credential returns HTTP `401`.

## Scope Management

An administrator can replace an identity's scopes with:

```text
PUT /agents/{agent_name}/scopes
```

Example:

```json
{
  "scopes": [
    "read_file",
    "search_logs"
  ]
}
```

Only actions defined in the GreyGuard policy can be assigned as scopes.

## Audit Evidence

The `audit_events` table records:

* Agent name
* Timestamp
* Action
* Policy decision
* Approval result
* Risk added
* Total risk
* Risk level
* Agent status
* Blocked attempts

The `authentication_events` table records:

* Claimed agent identity
* Authenticated identity
* Requested action
* Authentication or authorization outcome
* Security reason
* Timestamp

Credential values and credential hashes are not written to authentication-event records.

## Verified V9 Security Tests

V9 was manually verified through the running FastAPI application:

* Correct credential returned HTTP `200`
* Incorrect credential returned HTTP `401`
* Missing scope returned HTTP `403`
* Adding the scope allowed the request to reach policy enforcement
* `send_email` remained blocked by policy after scope authorization
* Credential rotation invalidated the old credential
* New rotated credential authenticated successfully
* Credential revocation rejected the newest credential
* Authentication events recorded success and failure
* Scope events recorded allowed and denied outcomes
* Existing V8 audit records remained intact
* Terminal mode continued to run
* Python compilation succeeded

## Version History

### Version 1 — Basic Policy

* Added `ALLOW`, `ASK`, and `BLOCK`

### Version 2 — Block Tracking

* Counted blocked attempts
* Added automatic suspension

### Version 3 — Risk Scoring

* Added weighted risk and risk levels

### Version 4 — Human Approval

* Added approved and denied outcomes

### Version 5 — Administrative Reset

* Added PIN-protected reset and persistent state

### Version 6 — SQLite Audit History

* Added database-backed security evidence

### Version 7 — Multi-Agent Control

* Added independent state for multiple agents

### Version 8 — FastAPI Control Plane

* Added REST endpoints and interactive documentation

### Version 9 — Identity and Scope Boundaries

* Added unique agent credentials
* Added salted credential hashing
* Added credential authentication
* Added per-agent scopes
* Added credential rotation and revocation
* Added `401` and `403` security boundaries
* Added authentication-event evidence
* Prevented agents from accessing other agents' records

## Security Limitations

GreyGuard V9 is a local defensive learning project.

Current limitations include:

* SQLite is intended for local development
* State is split between JSON and SQLite
* The administrator uses a PIN rather than a full user account
* Rate limiting is not yet implemented
* Agent credentials do not currently expire automatically
* Human approvals are not tied to authenticated human identities
* Tool execution remains simulated
* TLS is not configured for local development

Do not expose the development API directly to the public internet.

## Future Development

Possible future improvements include:

* Web security dashboard
* Authenticated administrator and approver accounts
* Expiring credentials
* Rate limiting and failed-login lockout
* Policy administration interface
* Resource-specific scopes
* Real-time security alerts
* Sandboxed tool execution
* GreyGuard integration with CanaryLab AI
* PostgreSQL deployment support
* Docker isolation
* Signed agent requests
* Multi-tenant organizational boundaries

## Safety Notice

GreyGuard is a defensive educational project. It evaluates and records simulated agent actions. It does not provide unrestricted operating-system, filesystem, browser, or network execution.

## Author

Michael Chukwujekwu Alughere
