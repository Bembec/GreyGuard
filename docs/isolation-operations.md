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

The scanning interface accepts an injected scanner adapter so production deployments can connect ClamAV or an enterprise malware service. Treat scanner errors as failed scans, retain the artifact in quarantine, and record the engine, result, and timestamp. Release workflows should require a separate authorized action.

## Emergency response

Activate the global kill switch when isolation controls, the container runtime, or an integration is suspected to be compromised. Terminate active sandbox jobs through Execution Isolation, preserve their evidence, rotate affected credentials, and investigate before restoring admission.
