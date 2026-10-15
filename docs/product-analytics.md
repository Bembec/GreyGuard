# Product analytics

Customer success needs to know whether an org is using GreyGuard, without learning anything about what that org's agents did. `backend/app/product_analytics.py` gives exactly that, and nothing more. The roadmap requires that product analytics exclude prompts, secrets and sensitive payloads, and that it can be turned off.

## What is computed

`GET /organizations/{org_id}/adoption` is available to the org's owners and to install operators. It covers the last 30 days and returns **counts only**:

- agents, and active agents (agents that made a request);
- controlled requests, and their split by decision;
- approvals decided;
- configured integrations and active gateways;
- compliance reports generated and org exports taken;
- members, and members who signed in.

These counts come from data the product already holds. Nothing extra is collected for them.

## What is collected

Exactly one thing: a **daily page-view count per org and page path**.

- **Paths are fixed navigation paths only**, such as `/agents` or `/live`. The server rejects anything else: identifiers, query strings, full URLs, or characters outside lowercase letters, digits and hyphens. The browser sends nothing for any page that isn't an exact navigation path.
- **The count has no user, session or IP address attached.**
- At most 100 paths per org per day are kept, for at most 400 days.
- **The browser honours Do Not Track** and sends nothing when it is set.

## What is never collected

- agent prompts, request targets and payloads;
- tool results;
- secrets and credentials;
- user, session and IP identifiers;
- page URLs beyond fixed navigation paths.

The adoption response repeats this list as `never_collected`. A test checks that adoption output contains no request target, payload, agent name or integration detail.

## Turning it off

| Scope | How | Effect |
|---|---|---|
| Whole install | `GREYGUARD_PRODUCT_ANALYTICS=off` | Nothing is collected for any org. Adoption counts remain available, because they come from existing data. |
| One org | `PUT /organizations/{org_id}/analytics` with `{"enabled": false}` (owners or install operators) | Collection stops for that org, and its page-view counts already collected are deleted. |

Page-view counts are org data. They are included in the org's export, and removed when the org is deleted.
