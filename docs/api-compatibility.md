# API and SDK compatibility

## API versions

| Version | Paths | Status |
|---|---|---|
| **v1** | `/api/v1/...` | Current. The only supported version. |
| Unversioned (legacy) | `/...` | Deprecated. Served until the sunset date of **2028-01-01**. |

`backend/app/api_versioning.py` implements the following:

- `/api/v1/<path>` is served by the same handler as `/<path>`. Every security middleware sees the canonical path, so versioning cannot route around a control.
- Every response carries `X-GreyGuard-API-Version: 1`.
- Responses on legacy unversioned paths also carry `Deprecation: true`, `Sunset: Sat, 01 Jan 2028 00:00:00 GMT` and `Link: </api/v1>; rel="successor-version"`.
- `GET /api/version` reports the current and supported versions, and the legacy sunset date.

## What a version promises

Within a major version (v1):

- Existing paths, methods, request fields and response fields are not removed or renamed.
- The meaning of an existing field does not change.
- Any of the following may be added at any time, so clients must ignore unknown response fields:
  - new optional request fields;
  - new response fields;
  - new routes;
  - new enum values in responses, such as a new `restriction_reasons` value or a new component on the status page.
- **Security fixes are the exception.** A response that leaked data, or an operation that was wrongly allowed, is corrected without a version change. Examples: P2.5 narrowed the compliance-report roster to the org's members, and P2.6 fixed JSON redaction. Each such change is called out in the release notes.
- **A refusal is not a break.** A newly denied action (`403` with `reason` `ENTITLEMENT` or `OFFBOARDING`) is the product enforcing a rule. It is not an incompatible change.

A breaking change needs a new major version (`/api/v2`), served alongside v1.

## Deprecation policy

1. A deprecation is announced in the release notes and in the API reference.
2. Deprecated behaviour stays available for at least **12 months** after the announcement, and for the life of any customer contract that names it.
3. Responses that use a deprecated path carry `Deprecation`, `Sunset` and `Link` headers for the whole period.
4. Removal happens only on a major version, or at the announced sunset date.

## SDK compatibility matrix

| SDK | Version | API | Notes |
|---|---|---|---|
| Python `greyguard-sdk` | 0.1.0 | v1 | `greyguard_sdk.gateway` needs the `gateway` extra (`cryptography`). |
| JavaScript `greyguard-sdk` | 0.1.0 | v1 | |
| Backend admin and agent clients (`backend/sdk`) | in-repo | v1 | Used by the project's own tests and tools. |

The SDKs are pre-1.0. Their own interfaces may still change between minor versions; the HTTP API they speak follows the v1 promise above.

**Gateway bundles** carry their own schema (`greyguard.gateway.bundle.v1`). A gateway must refuse a schema it does not know. A new bundle schema will be served alongside the old one for at least the 12-month deprecation period.
