# Controlled execution and isolation

GreyGuard's Docker sandbox is disabled by default and accepts only predefined job identifiers. It does not accept shell commands, executable code, arbitrary images, URLs or host paths.

The sandbox profile runs as UID/GID 65532 with a read-only root filesystem, a small `noexec` temporary workspace, no network, no added capabilities, `no-new-privileges`, a restrictive seccomp policy, a 64-process ceiling, 0.5 CPU, 256 MB memory and a 30-second application timeout. Limits are configurable only within bounded ranges.

The API builds Docker arguments as a fixed list and never invokes a shell. Execution results and termination evidence are stored. Emergency termination targets only containers registered by the active GreyGuard process.

Build the image with `docker compose -f docker-compose.production.yml --profile sandbox build sandbox-runner`. Validate configuration before use with `docker compose -f docker-compose.production.yml --profile sandbox config -q`.

Do not mount the Docker socket into the GreyGuard backend. A production execution worker should be separately isolated and narrowly authorized. Network access remains disabled; destination allowlisting belongs to a later explicitly approved integration.
