# Founder decisions required

<!-- Generated from config/decisions.json by `python scripts/decisions.py render`. Do not edit by hand:
     change the registry and re-render. backend/tests/test_decision_registry.py keeps the two in step. -->

Every decision GreyGuard needs from its owner or a professional adviser, what the product does safely until
it is made, and where the final value goes. Engineering does not guess these. When a decision is made, record
it in `config/decisions.json` (value, status `decided`, date and evidence) and re-render this file.

Readiness: `python scripts/decisions.py readiness --target production` lists exactly what blocks a production
publication, with how to resolve each item. Development and preview builds never require these decisions.

## Brand

| ID | Decision required | Safe behaviour until decided | Configured in | Blocks public launch | Professional review | Owner | Status | Decided | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| BRAND-NAME | What is the product and company name? | GreyGuard is used everywhere. | `config/decisions.json` | Yes — before public launch | — | Project owner | Decided | 2026-10-15 | docs/brand/GreyGuard_Brand_Guide.md |
| BRAND-01 | Which refined shield-G logo direction is final? | The approved brand-pack renders are used as provisional assets (config/brand-assets.json). | `config/brand-assets.json` | Yes — before public launch (blocks production once the brand is frozen, BRAND-06) | Brand designer | Project owner | Open | — | — |
| BRAND-02 | What is the final wordmark and complete asset system (horizontal, stacked, light, dark, monochrome, favicons, PWA icons, social preview)? | Missing slots fall back to the current approved renders; see config/brand-assets.json. | `config/brand-assets.json` | Yes — before public launch (blocks production once the brand is frozen, BRAND-06) | Brand designer | Project owner | Open | — | — |
| BRAND-03 | Has a trademark and distinctiveness review cleared the name and mark? | No trademark claim is made; the name and mark are used without the ® or ™ symbols. | `config/decisions.json` | Yes — before public launch | Trademark counsel | Project owner | Open | — | — |
| BRAND-04 | What is the tagline? | The brand pack's tagline is used. | `config/decisions.json` | No | — | Project owner | Decided | 2026-10-15 | docs/brand/GreyGuard_Brand_Guide.md |
| BRAND-05 | Are the product-group names (Gate, Watch, Respond, Evidence) final after buyer testing and a trademark search? | The working names appear on the preview site and in the console. | `config/decisions.json` | Yes — before public launch | Trademark counsel | Project owner | Open | — | — |
| BRAND-06 | Is the brand frozen for launch (so final logo assets become production-blocking)? | Not frozen: provisional logo assets are allowed. | `config/decisions.json` | No | — | Project owner | Open | — | — |

## Commercial

| ID | Decision required | Safe behaviour until decided | Configured in | Blocks public launch | Professional review | Owner | Status | Decided | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| COM-01 | What are the final plan names? | Working names Foundation, Enterprise and Dedicated are internal hypotheses (P4); the public site shows "Contact sales". | `backend/app/entitlements.py PLANS` | No | — | Project owner | Open | — | — |
| COM-02 | What are the final prices and billing intervals? | No prices are shown anywhere; the site says "Contact sales". | `config/decisions.json` | No | — | Project owner | Open | — | — |
| COM-03 | Is there a pilot fee, and how much (P4 decision D3)? | No fee or price field exists for pilots. | `config/decisions.json` | No | — | Project owner | Open | — | — |
| COM-04 | Who are the design partners (P4 decision D10), and may they be named? | No customer or partner is named anywhere. | `config/decisions.json` | No | Legal counsel (written consent to be named) | Project owner | Open | — | — |
| COM-05 | What are the Dedicated-edition contract limits and the Foundation and Enterprise limit values (P4 decision D6)? | Dedicated limits are entered per contract when a plan is assigned; Foundation and Enterprise values are provisional. | `backend/app/entitlements.py PLANS` | No | — | Project owner | Open | — | — |
| COM-06 | Is a trial offered, and for how long? | Only the 90-day pilot (P4 decision D2) exists; no self-serve trial is offered. | `config/decisions.json` | No | — | Project owner | Open | — | — |
| COM-07 | Where do demo and sales requests go (P7 decision W5)? | "Request a demo" opens /request-demo/, which explains that online requests are not open yet. No request is collected, so none can be lost. | `config/decisions.json` | Yes — blocks production | — | Project owner | Open | — | — |

## Public company information

| ID | Decision required | Safe behaviour until decided | Configured in | Blocks public launch | Professional review | Owner | Status | Decided | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| CO-01 | What is the production domain for the public site (P7 decision W4)? | Preview builds use https://preview.greyguard.invalid and are never indexed. | `config/decisions.json`, env `GREYGUARD_SITE_URL` | Yes — blocks production | — | Project owner | Open | — | — |
| CO-02 | What is the public support email? | No support address is published; support pages say it is coming. | `config/decisions.json` | Yes — before public launch | — | Project owner | Open | — | — |
| CO-03 | What is the security contact? | — | `config/decisions.json` | Yes — blocks production | — | Project owner | Decided | 2026-10-15 | docs/roadmap/p6-decision-package.md (T3) |
| CO-04 | Which monitored security mailbox will be added before public launch (T3 follow-up)? | The private advisory form (CO-03) is the only security contact. | `config/decisions.json` | Yes — before public launch | — | Project owner | Open | — | — |
| CO-05 | What is the legal entity name? | The footer says "GreyGuard" without a legal entity. | `config/decisions.json` | Yes — before public launch | Legal counsel | Project owner | Open | — | — |
| CO-06 | Is a registered address required on the site, and what is it? | No address is published. | `config/decisions.json` | No | Legal counsel | Project owner | Open | — | — |
| CO-07 | Which social-media accounts should be linked? | No social links are shown. | `config/decisions.json` | No | — | Project owner | Open | — | — |
| CO-08 | What is the public status-page address? | The site's Status page explains that live status is published by the application at /status. | `config/decisions.json` | Yes — before public launch | — | Project owner | Open | — | — |

## Legal and trust

| ID | Decision required | Safe behaviour until decided | Configured in | Blocks public launch | Professional review | Owner | Status | Decided | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| LEG-01 | Is the privacy notice approved? | The privacy page is a draft shell, labelled as a draft in preview and never indexed; production publication is blocked. | `website/src/pages/legal/privacy.astro + LEG-01` | Yes — blocks production | Legal counsel | Project owner | Open | — | — |
| LEG-02 | Are the terms approved? | Draft shell, labelled in preview; publication blocked. | `website/src/pages/legal/terms.astro + LEG-02` | Yes — blocks production | Legal counsel | Project owner | Open | — | — |
| LEG-03 | Is the cookie notice approved, and is consent required (the site sets no cookies and has no analytics today)? | Draft shell, labelled in preview; publication blocked. | `website/src/pages/legal/cookies.astro + LEG-03` | Yes — blocks production | Legal counsel (GDPR and KVKK) | Project owner | Open | — | — |
| LEG-04 | Is the data-processing agreement approved? | No DPA is offered; customer data is not accepted for paid use. | `config/decisions.json` | Yes — before public launch | Legal counsel | Project owner | Open | — | — |
| LEG-05 | Which subprocessors are approved for the hosted offering (P6 decision T6)? | Subprocessors are "not selected"; the page is a draft shell and publication is blocked. | `website/src/pages/legal/subprocessors.astro + LEG-05` | Yes — blocks production | Legal counsel | Project owner | Open | — | — |
| LEG-06 | What is the responsible-disclosure contact? | — | `config/decisions.json` | Yes — blocks production | — | Project owner | Decided | 2026-10-15 | docs/roadmap/p6-decision-package.md (T3) |
| LEG-07 | Are the public claims approved? | Every claim is "proposed"; preview builds mark them and a publish build refuses any unapproved claim. | `website/content/claims.json` | Yes — blocks production | — | Project owner | Computed | — | — |
| LEG-08 | Is insurance in place, and may it be stated publicly? | Insurance is not mentioned anywhere. | `config/decisions.json` | No | Insurance broker | Project owner | Open | — | — |
| LEG-09 | Will SOC 2 or ISO 27001 be pursued, and when? | The Trust page says "Not currently claimed"; no certification is implied. | `config/decisions.json` | No | Auditor | Project owner | Open | — | — |
| LEG-10 | Has legal counsel approved the site for publication? | Publication is blocked. | `config/decisions.json` | Yes — blocks production | Legal counsel | Project owner | Open | — | — |
| LEG-11 | Is the accessibility statement approved (after the P7.5 audit)? | The accessibility page says the statement follows the audit. | `website/src/pages/accessibility.astro + LEG-11` | Yes — before public launch | — | Project owner | Open | — | — |

## Operations

| ID | Decision required | Safe behaviour until decided | Configured in | Blocks public launch | Professional review | Owner | Status | Decided | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| OPS-01 | Which versions are supported, and for how long? | The API compatibility policy applies; no support window is promised. | `config/decisions.json` | Yes — before public launch | — | Project owner | Open | — | — |
| OPS-02 | What are the support hours? | No support hours are published. | `config/decisions.json` | Yes — before public launch | — | Project owner | Open | — | — |
| OPS-03 | What support response targets will be committed? | No response targets or SLA are promised. | `config/decisions.json` | Yes — before public launch | — | Project owner | Open | — | — |
| OPS-04 | Which hosting provider runs production (P7 decision W4, P6 decision T6)? | Nothing is deployed. | `config/decisions.json` | Yes — blocks production | Legal counsel (subprocessor terms) | Project owner | Open | — | — |
| OPS-05 | Which production region holds customer data? | Nothing is deployed. | `config/decisions.json` | Yes — blocks production | — | Project owner | Open | — | — |
| OPS-06 | What backup-retention values apply to the hosted service? | Self-hosted operators set their own retention; nothing is promised for a hosted service. | `config/decisions.json` | Yes — before public launch | — | Project owner | Open | — | — |
| OPS-07 | What public availability commitments will be made? | None: availability is not promised until measured (docs/reliability.md). | `config/decisions.json` | No | — | Project owner | Open | — | — |
| OPS-08 | Who are the customer escalation contacts? | No escalation contacts are published. | `config/decisions.json` | Yes — before public launch | — | Project owner | Open | — | — |
| OPS-09 | Are production secrets and deployment settings configured? | Development and preview need none. | `Deployment environment`, env `GREYGUARD_BOOTSTRAP_EMAIL,GREYGUARD_BOOTSTRAP_PASSWORD,GREYGUARD_ALLOWED_ORIGINS,GREYGUARD_TRUSTED_HOSTS,GREYGUARD_DATABASE_URL` | Yes — blocks production | — | Project owner | Computed | — | — |
