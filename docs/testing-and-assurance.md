# Testing and assurance

GreyGuard Roadmap Section 12 Part 1 establishes a fixed security regression matrix across backend and frontend controls.

Run the complete matrix from the repository root with `python scripts/run_security_assurance.py`. A single backend group can be selected with `--group`; command input is restricted to predefined group names and the runner never invokes a shell.

The matrix maps authentication, authorization, cross-agent isolation, scope boundaries, approval bypass, replay and race safety, path traversal, symlink escape, credential redaction, rate limiting, and audit integrity to existing regression files. GitHub Actions runs backend groups independently and runs the complete frontend component and workflow suite.

A failed group blocks assurance completion. Preserve its output with the related change, correct the regression, rerun the affected group, then rerun the full matrix. Tests must never use production secrets, identities, destinations, or evidence databases.

Part 2 adds dependency, static-code, secret, container, and SBOM scanning plus threat-model, abuse-case, backup, kill-switch, and disaster-recovery exercises.
