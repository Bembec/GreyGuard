// Derives the website's web-sized brand files from config/brand-assets.json (the one manifest the
// console uses too), and writes src/lib/brand-assets.generated.json for the components. Pages ask
// for a slot; replacing artwork means updating the manifest and running `npm run brand`.
import { mkdirSync, readFileSync, rmSync, writeFileSync, copyFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import sharp from "sharp"

const website = join(dirname(fileURLToPath(import.meta.url)), "..")
const root = join(website, "..")
const manifest = JSON.parse(readFileSync(join(root, "config", "brand-assets.json"), "utf8"))
const source = join(root, manifest.source_root)
const out = join(website, "public", "brand")
const NAVY = "#050a12"

function resolve(name) {
  const seen = []
  let current = name
  for (;;) {
    if (seen.includes(current)) throw new Error(`fallback loop for ${name}`)
    seen.push(current)
    const slot = manifest.slots[current]
    if (slot.status !== "missing") return { slot, from: current, provisional: slot.status !== "final" || current !== name }
    current = slot.fallback
  }
}

// What the website renders, and the web size each is derived at.
const outputs = {
  "lockup-dark": { width: 480 },
  "symbol": { width: 256 },
  "apple-touch-180": { copy: true },
  "favicon-ico": { copy: true },
  "social-preview": { canvas: [1200, 630] },
}

rmSync(out, { recursive: true, force: true })
mkdirSync(out, { recursive: true })
const generated = { generatedFrom: "config/brand-assets.json", slots: {} }
for (const [name, plan] of Object.entries(outputs)) {
  const { slot, from, provisional } = resolve(name)
  const input = join(source, slot.path)
  const extension = slot.path.split(".").pop()
  if (plan.copy) {
    const file = `${name}.${extension}`
    copyFileSync(input, join(out, file))
    generated.slots[name] = { path: `/brand/${file}`, webp: null, width: slot.width ?? null, height: slot.height ?? null, resolvedFrom: from, provisional }
    continue
  }
  if (plan.canvas) {
    const [width, height] = plan.canvas
    const image = from === name
      ? sharp(input).resize({ width, height, fit: "cover" })
      : sharp(input).resize({ width: Math.round(width * 0.8), height: Math.round(height * 0.8), fit: "contain", background: NAVY })
          .extend({ top: Math.round(height * 0.1), bottom: Math.round(height * 0.1), left: Math.round(width * 0.1), right: Math.round(width * 0.1), background: NAVY })
    const buffer = await image.png().toBuffer()
    const fitted = await sharp(buffer).resize({ width, height, fit: "contain", background: NAVY }).png().toFile(join(out, `${name}.png`))
    generated.slots[name] = { path: `/brand/${name}.png`, webp: null, width: fitted.width, height: fitted.height, resolvedFrom: from, provisional }
    continue
  }
  const resized = sharp(input).resize({ width: plan.width })
  const png = await resized.clone().png({ compressionLevel: 9 }).toFile(join(out, `${name}.png`))
  await resized.clone().webp({ quality: 90 }).toFile(join(out, `${name}.webp`))
  generated.slots[name] = { path: `/brand/${name}.png`, webp: `/brand/${name}.webp`, width: png.width, height: png.height, resolvedFrom: from, provisional }
}
writeFileSync(join(website, "src", "lib", "brand-assets.generated.json"), JSON.stringify(generated, null, 2) + "\n")
console.log(`Brand assets derived: ${Object.keys(generated.slots).join(", ")}`)
