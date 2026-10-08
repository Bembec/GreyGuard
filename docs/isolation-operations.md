# Isolation operations

GreyGuard Section 10 Part 2 extends the hardened execution sandbox with lifecycle controls for per-agent workspaces, artifact quarantine, restricted network policy, Kubernetes jobs, and emergency admission shutdown.

## Operational boundaries

- Each agent receives a validated workspace beneath GreyGuard's isolated workspace root. Names and resolved paths are checked before creation or deletion.
- Workspace destruction is explicit, recorded, and irreversible. Quarantined artifacts are stored outside the active workspace.
- Artifacts remain quarantined after scanning. A clean result records evidence but never automatically releases a file.
- Network access remains disabled by default. Enabling it requires both destination and DNS allowlists.
- The global kill switch blocks new workspaces and Kubernetes jobs without deleting existing evidence.

## Kubernetes isolation

Generated jobs use the `greyguard-sandbox` namespace and `greyguard-sandbox-runner` service account. Service-account token mounting is disabled. Containers run as a non-root user with a read-only root filesystem, dropped Linux capabilities, RuntimeDefault seccomp, resource limits, an ephemeral workspace, no retries, and automatic cleanup.

Apply `deployment/kubernetes/sandbox-namespace.yaml` before submitting generated jobs. The included NetworkPolicy denies ingress and egress by default. Add narrowly scoped egress policies only for reviewed destination and DNS allowlists.

## Host mandatory access control

Docker hosts should load `deployment/apparmor/greyguard-sandbox` and assign it to the sandbox container. On SELinux hosts, keep enforcing mode enabled and use a container-specific domain with write access limited to the temporary workspace and quarantine mount. Do not disable AppArmor or SELinux to resolve deployment failures.

## Malware scanning

`POST /isolation-operations/workspaces/{workspace_id}/artifacts` writes the given bytes into that agent's isolated workspace and immediately quarantines them (`isolation_operations.write_and_quarantine_artifact`) - the content is never opened, parsed, executed, or rendered at any point, only hashed and stored. Content is capped at 1,000,000 bytes at the API layer, independent of quarantine's own 10,000,000 byte cap.

`POST /isolation-operations/artifacts/{artifact_id}/scan` scans a quarantined artifact. Both endpoints require Platform Administrator permission.

Scanning is **disabled by default** (`GREYGUARD_MALWARE_SCANNING_ENABLED` must be set to `true`); the scan endpoint fails closed with 403 before ever attempting to reach a scanner if it is not. `backend/app/malware_scanner.py` is a clearly isolated adapter: it speaks ClamAV's `clamd` `INSTREAM` wire protocol directly over a TCP socket (`GREYGUARD_CLAMD_HOST`/`GREYGUARD_CLAMD_PORT`, default `127.0.0.1:3310`) with bounded connect/total timeouts and its own size cap, matching quarantine's 10 MB limit. `isolation_operations.py` has no ClamAV-specific code at all - `scan_artifact` accepts any callable shaped `Path -> {"engine","clean","detail"}`, which is also how its tests exercise the quarantine/evidence logic without a live scanner.

A scanner that cannot be reached, times out, or returns a response this adapter cannot confidently interpret raises rather than returning a result - `scan_artifact` catches that and records the artifact as `SCAN_FAILED`, never `CLEAN`. An artifact is only ever `CLEAN` after an explicit "no threat found" response from a scanner that was actually reached. Release workflows should require a separate authorized action; nothing here automatically returns a `CLEAN` artifact to active use.

## Emergency response

Activate the global kill switch when isolation controls, the container runtime, or an integration is suspected to be compromised. Terminate active sandbox jobs through Execution Isolation, preserve their evidence, rotate affected credentials, and investigate before restoring admission.
