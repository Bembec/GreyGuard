# GreyGuard SDK Developer Guide

GreyGuard provides supported Python and JavaScript/TypeScript clients for
agents that need policy-controlled access to tools. Both SDKs implement the
same security contract: local scope validation, redacted credentials, bounded
timeouts, typed failures, and idempotent retries for tool submissions.

## Documentation

- [Quick start](quickstart.md)
- [Security practices](security.md)
- [API reference](api-reference.md)
- [Troubleshooting](troubleshooting.md)

## Supported clients

| Client | Runtime | Package location |
| --- | --- | --- |
| Python | Python 3.10+ | `sdk/python` |
| JavaScript/TypeScript | Node.js 18+ | `sdk/javascript` |

Use server-side or otherwise trusted runtimes. Never place an agent credential
inside public browser bundles, mobile applications, source control, screenshots,
or client-visible error messages.
