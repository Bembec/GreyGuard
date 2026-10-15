import "../../styles/brand.css"

import { brandAsset, type BrandSlot } from "./brandAssets"

type LogoVariant = "primary" | "horizontal" | "symbol"

/** Each variant is a slot in config/brand-assets.json; the file behind it can change without code changes. */
const SLOTS: Record<LogoVariant, BrandSlot> = {
  primary: "lockup-dark",
  horizontal: "lockup-horizontal-dark",
  symbol: "symbol",
}

interface LogoProps {
  variant: LogoVariant
  className?: string
}

/**
 * GreyGuard's logo, by slot. The current approved artwork has a baked-in navy background (the
 * brand pack supplies no transparent or light-background variant yet), so every usage renders
 * inside a fixed-navy chip in both themes - see docs/brand/GreyGuard_Brand_Guide.md.
 */
export function Logo({ variant, className }: LogoProps) {
  const asset = brandAsset(SLOTS[variant])
  return (
    <span className={["gg-logo", `gg-logo--${variant}`, className ?? ""].join(" ").trim()} data-brand-slot={asset.slot}>
      <picture>
        {asset.webp && <source srcSet={asset.webp} type="image/webp" />}
        <img src={asset.path} width={asset.width ?? undefined} height={asset.height ?? undefined} alt="GreyGuard" />
      </picture>
    </span>
  )
}

/** The symbol-only mark. */
export function BrandMark({ className }: { className?: string }) {
  return <Logo variant="symbol" className={className} />
}

/** The full lockup. */
export function BrandLockup({ className, compact = false }: { className?: string; compact?: boolean }) {
  return <Logo variant={compact ? "horizontal" : "primary"} className={className} />
}
