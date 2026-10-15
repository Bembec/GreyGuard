# P7 decision package — Separate public commercial website

**Status: awaiting the owner's approval. Not started.** The addendum requires Michael's approval before each major workstream starts, before any dependency changes and before a website is published. This package scopes P7 against what exists in this repository today, so that the approval covers a defined piece of work. It also proposes when the application's information architecture redesign (P1.4) should run. Nothing here is built, deployed or published.

## Decision record

| # | Decision | Recommendation | Why |
|---|---|---|---|
| W0 | When the P1.4 information architecture redesign runs | **Before P7 starts**, as its own approved workstream. | Every P7 product page needs a real or clearly synthetic product visual. Screenshots taken before the redesign would all need redoing. P8 also depends on a stable authenticated app. If the owner prefers P7 first, P1.4 must still finish before P8 and before final acceptance. |
| W1 | Start P7 | **Yes, once W0 is settled. Build the site source only.** Publishing is a separate approval (W11). | P6 put the Trust Center source in this repository so it could be published with P7. |
| W2 | Where the site lives | **A top-level `website/` directory with its own package, lockfile, build and CI job.** It imports nothing from `frontend/` or `backend/`, and it can move to its own repository before publishing. | The addendum requires deployment and infrastructure kept separate from the application. A separate directory keeps claims next to the evidence they cite while the site is being written. |
| W3 | Site technology (a new dependency) | **A static site generator producing plain HTML: Astro, at an exact version.** | The addendum asks for static-first CDN delivery and good mobile Core Web Vitals. Astro sends no JavaScript by default. It is a new dependency, so it needs approval. |
| W4 | Hosting, CDN and domain | **Owner to choose.** No deployment until they are chosen. | These are vendor choices, and T6 left vendors TBD. I won't pick one. |
| W5 | Demo and design-partner requests | **A call to action pointing to a contact the owner supplies.** No form backend until a provider and a handling process are chosen. | A live form needs spam and abuse controls, a data processor and a privacy notice. None of these exist yet. |
| W6 | Analytics | **None at launch.** | This meets the privacy requirement without a consent banner, and consent withdrawal stays trivial. Analytics that respect privacy can be added later as a separate decision. |
| W7 | Claim register | **Bring it forward from P8 to P7.0.** Every product statement on the site comes from a register entry with its scope, evidence, owner, approval date and review date. | The site makes claims as soon as it has content. The addendum forbids unsourced claims and requires each capability to be labelled verified, pilot, preview or planned. |
| W8 | Legal pages | **Page shells only, marked as not publishable** until counsel delivers the documents (T7). | Privacy, Terms, Cookies and Subprocessors need qualified review. Responsible Disclosure can link to `security.txt` and the T3 contact. |
| W9 | Product visuals | **Screenshots of the real app running on synthetic, isolated data, each labelled as synthetic**, plus artwork from the approved brand pack. | The addendum allows only real or clearly synthetic visuals. It forbids fabricated customers, logos and metrics. |
| W10 | Language | **English first**, with routes and content ready for localization. | This is the addendum's requirement. Translations are a later decision. |
| W11 | Publishing | **A separate owner approval**, after the P7.5 acceptance run and once W4, W5 and W8 are resolved. | The addendum requires approval before a website is published. |

## Proposed sub-phases (if approved)

Each sub-phase gets one `feat:` commit and one `docs:` commit recording its verification, as earlier phases did.

| Sub-phase | Scope | Verification |
|---|---|---|
| P7.0 | Claim register and content model. Each capability is mapped to its evidence and availability label. | Every entry cites a file or test that exists. A check fails the build on any claim that isn't registered. |
| P7.1 | Site skeleton, the navigation required by the addendum, security headers (CSP, HSTS and others), dependency and secret scanning in CI | Header tests; the build produces static output only; no CMS or admin surface |
| P7.2 | Homepage, following the addendum's ten-step sequence, and the Gate, Watch, Respond and Evidence pages | Each product page covers all nine required elements; claim check passes |
| P7.3 | Agent environments, integrations, use cases and resources | Each connection method shows its coverage boundaries, using the coverage matrix |
| P7.4 | Proof and Trust pages linking to the `docs/trust/` source, legal page shells, accessibility statement, sitemap, canonical URLs | Link check; legal shells blocked from publishing |
| P7.5 | Acceptance | WCAG 2.2 AA audit, mobile Core Web Vitals, header scan and redirect tests |

## What P7 doesn't include

- Proof experiences and demos. These are P8 and need the claim register first.
- Sales material. This is P9.
- Any change to the application or its security boundaries. The site's sign-in link only goes to the application's own login page.
