# P7 owner's brief — what the website needs from you, and why

This brief is for the project owner. It explains the three website decisions only you can make,
so you can assess them before choosing: W4 (hosting, CDN and domain), W5 (how demo requests reach
you) and the approval of claims. Nothing here selects a vendor or quotes a price; vendors remain
"not selected" (T6) until you choose. Engineering can build and check the whole site without these
answers. Only publishing waits for them (W11).

## 1. How the site works

- **It is a set of static files.** The site is built once into plain HTML, CSS and images. No
  server program runs for it, and there is no database and no admin login to attack. This is why
  the addendum asks for "static-first/CDN": less to secure, cheap to run, fast everywhere.
- **It is completely separate from the console.** The site never talks to your GreyGuard install.
  Its "Sign in" link just opens the console's own login page. A problem with the site cannot
  affect customers' agents, and the reverse is true too.
- **Every product statement comes from the claim register.** That is `website/content/claims.json`
  (section 4).

## 2. Decision W4 — hosting, CDN and domain

**What you are choosing:**
- **A domain.** The address people type, for example `greyguard.<something>`. You buy it from a
  domain registrar and renew it yearly. Choose a name you can keep, and decide whether the console
  lives on a subdomain (for example `app.` or `console.`) of the same domain.
- **A static host with a CDN.** A service that stores the built files and serves them from many
  locations worldwide. Common kinds:
  - **Static-site platforms:** connect to the repository and publish on each approved change.
    These are the simplest.
  - **Cloud object storage with a CDN in front:** the most control, and the most setup.
  - **Git-hosting pages:** the simplest option, but with fewer controls over security headers.

**What to look for when you assess them:**

| Need | Why it matters here |
|---|---|
| Custom security headers (CSP, HSTS and others) | The addendum requires them, and some hosts limit what you can set |
| Automatic HTTPS for your domain | Required |
| Preview deployments that are not public | So you can review a page before it goes live |
| Where the provider stores logs and visitor data | GDPR/KVKK. It also becomes a subprocessor in the Trust Center (T6). |
| Who can publish | Publishing should need your approval (W11), not happen on every change |

**My recommendation:**
- Pick a static-site platform that allows custom headers and private previews. It is the least
  work and covers every requirement above.
- Register the domain in an account you control, not in a contractor's account.

## 3. Decision W5 — demo and design-partner requests

**What you are choosing:** where a "request a demo" goes. The options, simplest first:

1. **An email link to a monitored address.** No form, no data stored by the site, and nothing to
   protect from spam bots. This is the recommended choice for launch.
2. **A booking link** to a scheduling service. The visitor picks a time, and that service becomes a
   subprocessor.
3. **A form.** This needs a form service or a small backend, spam and abuse protection, a privacy
   notice that covers it, and a retention rule for what people submit. It is the most work and the
   most legal exposure.

Option 1 can change to 2 or 3 later without redesigning the site.

## 4. Approving claims

- **What a claim is.** The register currently holds **29 proposed claims**, and every one shows
  its scope and evidence. Each verified capability is backed by a named automated test, and four
  are limitations the site must state honestly. One claim, monitor-only connection, is labelled
  **planned**, because it is not built.
- **How approval works.** Nothing is published until you approve it. For each claim you can:
  - **approve it** as written;
  - **edit the wording**, as long as it stays true to the evidence;
  - **leave it proposed**, so it stays off the site.
- **What the site does with your choices.** It shows only approved claims, each with its
  availability label (verified, pilot, preview or planned).
- **The words to treat with care:** "partner", "certified", "compliant" and "guaranteed". The
  register's check refuses them in claim text, because a working integration does not make a
  partnership, and GreyGuard holds no certification yet.

## 5. What happens next without your answers

| Step | Needs from you | Status |
|---|---|---|
| P7.1 Site skeleton, navigation, security headers, scanning in CI | Nothing | Next |
| P7.2–P7.4 Pages: homepage, product groups, connection methods, trust, legal page shells | Nothing; pages use only approved claims and show placeholders until then | After P7.1 |
| P7.5 Accessibility, mobile performance and header checks | Nothing | After P7.4 |
| Publishing (W11) | The domain and host (W4), the demo route (W5), approved claims, and counsel's legal pages (W8, T7) | Waits for you |
