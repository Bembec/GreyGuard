# Subprocessors and external services

## What the software itself contacts

- **No built-in external destination.** The backend contains no external address of its own, and a test enforces this. It sends no telemetry to GreyGuard or anyone else [TC-SUB-1].
- **Outbound connections go only where the operator or the customer points them** [TC-SUB-2]:

| Connection | Configured by | Purpose |
|---|---|---|
| OIDC identity provider | Customer | Single sign-on, and fetching the provider's signing keys |
| Secret manager (Vault, AWS, Azure, Google) | Operator or customer | Resolving integration secrets just in time |
| SIEM and observability destinations | Customer | Security evidence exports |
| Jira or ServiceNow | Customer | Incident records |
| Slack, Microsoft Teams, PagerDuty or Opsgenie | Customer | Notifications |

Systems a customer connects are the customer's own. They are not GreyGuard subprocessors (decision T6).

- **Billing.** The only billing provider implemented is a sandbox mock, which is refused in production. No payment processor is integrated, and card data is never stored [TC-SUB-3].
- **Email.** Email delivery is not built. The email notification channel refuses to send rather than sending silently [TC-SUB-4].

## Vendors for the hosted offering

**Not yet chosen.** The project owner will supply these (decision T6). Until then, no subprocessor is claimed [TC-SUB-5].

| Category | Vendor | Region | Data processed |
|---|---|---|---|
| Hosting and database | Not yet chosen | — | — |
| Transactional email | Not yet chosen | — | — |
| Customer support tooling | Not yet chosen | — | — |
| Payment processing | Not yet chosen | — | — |

## Software supply chain

Source code, CI and the container registry are on GitHub. GitHub builds and stores the software; it does not process customer data from a running install [TC-SUB-6].
