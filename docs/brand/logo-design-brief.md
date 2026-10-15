# GreyGuard logo — design brief

For a professional brand or logo designer. Prepared 2026-10-15.

## Background

GreyGuard is a security control plane for AI agents. It decides what an AI agent may do, brings
a person in for consequential actions, and keeps tamper-evident evidence. Buyers are security leaders
(CISOs, security operations, AI platform owners), so the brand must read as precise, trustworthy and
enterprise-grade.

The current logo, a shield-shaped "G" above the GREYGUARD wordmark with the tagline
SECURE • MONITOR • CONTROL, was created before the website and application existed. It exists only
as photorealistic 3D renders (brushed metal and blue glow) baked onto dark rectangles
(`docs/brand/`, `frontend/public/brand/logos/`). It works as a splash image. It does not work as a
working logo:

- It cannot sit on any background without its box showing.
- The wordmark becomes unreadable below about 160 px wide, which is a website header's size.
- There is no light-background version, no single-colour version, and no favicon that reads at 16 px.

## What we need

1. **A refined mark.** Keep the recognisable idea, a shield formed from a "G", but redraw it as a
   clean, flat, geometric symbol. Reduce detail until it holds at 16 px. No bevels or textures in
   the master; a separate optional "hero" rendering may keep the metallic style for splash screens.
2. **A wordmark.** GREYGUARD, legible at 120–160 px wide. The current split colouring (GREY in steel,
   GUARD in blue) can stay if it holds up at small sizes.
3. **Lockups.**
   - Horizontal: mark to the left of the wordmark, for website and application headers.
   - Stacked: mark above the wordmark, optionally with the tagline.
   - Symbol only: for favicons, app icons and avatars.
4. **Colour versions of each lockup:**
   - full colour on dark;
   - full colour on light;
   - single colour white;
   - single colour black;
   - greyscale.
5. **Files:**
   - SVG masters with outlined text, plus PDF or EPS for print;
   - transparent PNG and WebP exports at 1×, 2× and 4×;
   - a favicon set (16, 32 and 48 px, plus ICO);
   - Apple touch (180 px) and PWA (192 px, 512 px and maskable) icons;
   - a social preview (1200×630).
6. **Specifications:** clear space, minimum sizes, construction grid, exact colour values (HEX, RGB,
   CMYK and a spot colour), and do's and don'ts.

## Brand constraints

- **Palette (current tokens):**
  - Deep Navy `#050A12`
  - Security Blue `#0062C4`
  - Electric Glow `#48C8F8`
  - Steel Grey `#8C939A`
  - Light Steel `#E0E8E8`
  
  Refinement is welcome if you justify it.
- **Typography in the product:** Inter (body) and Saira (headings). The wordmark may be custom, but
  it must sit comfortably beside both.
- **Tagline:** exactly "SECURE • MONITOR • CONTROL", used only where it stays legible.
- **Tone:** calm, exact and engineered. Avoid gaming, military or hacker aesthetics.

## For reference

Study how leading security and developer-tool companies present their marks in a header:
flat, high-contrast and readable at small sizes on dark and light backgrounds. Wiz, Zenity, Lakera,
Snyk, 1Password, Cloudflare, Linear and Vercel are good examples. Do not imitate any of them.

## Before use

- The owner commissions a **trademark and distinctiveness search** for the name and the mark before
  registration or launch.
- The designer confirms that **all rights in the artwork transfer** to GreyGuard. No stock elements
  may be used without a licence.
- Once approved, the new files replace the renders in `docs/brand/` and
  `frontend/public/brand/`, and the website picks them up.
