# Testing and assurance

GreyGuard Roadmap Section 12 Part 1 establishes a fixed security regression matrix across backend and frontend controls.

Run the complete matrix from the repository root with `python scripts/run_security_assurance.py`. A single backend group can be selected with `--group`; command input is restricted to predefined group names and the runner never invokes a shell.

The matrix maps authentication, authorization, cross-agent isolation, scope boundaries, approval bypass, replay and race safety, path traversal, symlink escape, credential redaction, rate limiting, and audit integrity to existing regression files. GitHub Actions runs backend groups independently and runs the complete frontend component and workflow suite.

A failed group blocks assurance completion. Preserve its output with the related change, correct the regression, rerun the affected group, then rerun the full matrix. Tests must never use production secrets, identities, destinations, or evidence databases.

Part 2 adds dependency, static-code, secret, container, and SBOM scanning plus threat-model, abuse-case, backup, kill-switch, and disaster-recovery exercises.

## Tenant isolation and failure-safety acceptance suite

`backend/tests/test_tenant_acceptance.py` is the acceptance gate for multi-tenancy (roadmap P2.6). It does not list routes by hand: it reads the application's own route table and OpenAPI schema, so a route added later is covered automatically.

### Setup

Each sweep works with three orgs:

- **Attacker:** an org whose owner and agent probe the API.
- **Victim:** a populated tenant org.
- **Default org:** also populated, and also treated as a victim, because a route that forgets its `org_id` falls back to it.

### Read sweep

The attacker calls every `GET` route. Each path parameter is filled first with the victims' real identifiers, then with the attacker's own, because a leak can surface inside the attacker's own records.

A route fails if any of these is true:

- any victim identifier appears in the response, other than one the request itself echoes;
- a victim identifier the attacker supplied comes back with a 2xx status;
- the response is a 5xx.

### Write sweep

The attacker calls every `POST`, `PUT`, `DELETE` and `PATCH` route, with request bodies generated from the OpenAPI schema. Afterwards, every row each victim owns must be byte-for-byte unchanged, and no request may return a 5xx.

The sweep also requires that more than 150 calls reached a handler (were not rejected by request validation) and that more than 30 were accepted, so it cannot pass by exercising nothing.

### Failure matrix

For every restriction reason except `ORG_DELETED`, the matrix confirms over HTTP that each mandatory protection still works:

| Protection | Check |
|---|---|
| Agent identity | An existing agent still authenticates. |
| Authorization | An out-of-scope action is still blocked. |
| Redaction | A secret in an agent's request never appears in evidence. |
| Evidence | The audit log is still readable. |
| Emergency stop | Emergency stop still works. |
| Basic recovery | Agent reset still works. |
| Evidence export | Compliance reports, report export and the full org export still work. |
| Offboarding | Offboarding is still possible. |

It also confirms that new growth is refused. A separate test requires the protection checks to cover `MANDATORY_PROTECTIONS` exactly.

### Skipped routes

`SKIPPED_ROUTES` lists the few routes the sweeps never call, each with its reason:

- the provider-signed billing webhook;
- logout and refresh, which would end the probing session;
- the never-ending live event stream, which serves the same org-scoped query as `GET /audit-events`.

### Running it on PostgreSQL

The suite also passes against PostgreSQL. Run each test against a freshly migrated schema, with `GREYGUARD_DATABASE_URL` set.
