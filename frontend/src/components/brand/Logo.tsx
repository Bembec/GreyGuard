import "../../styles/brand.css"

type LogoVariant = "primary" | "horizontal" | "symbol"

const SOURCES: Record<LogoVariant, { webp: string; png: string; width: number; height: number }> = {
  primary: { webp: "/brand/logos/primary/greyguard-primary-stacked.webp", png: "/brand/logos/primary/greyguard-primary-stacked.png", width: 1839, height: 855 },
  horizontal: { webp: "/brand/logos/horizontal/greyguard-horizontal-dark.webp", png: "/brand/logos/horizontal/greyguard-horizontal-dark.png", width: 920, height: 610 },
  symbol: { webp: "/brand/logos/symbol/greyguard-symbol-dark.webp", png: "/brand/logos/symbol/greyguard-symbol-dark.png", width: 700, height: 700 },
}

interface LogoProps {
  variant: LogoVariant
  className?: string
}

/**
 * GreyGuard's approved raster logo marks. All three variants use a baked-in navy
 * background (the brand pack supplies no transparent or light-background variant),
 * so every usage renders inside a fixed-navy chip in both themes - see
 * docs/brand/GreyGuard_Brand_Guide.md ("approved for deep navy ... backgrounds").
 */
export function Logo({ variant, className }: LogoProps) {
  const source = SOURCES[variant]
  return (
    <span className={["gg-logo", `gg-logo--${variant}`, className ?? ""].join(" ").trim()}>
      <picture>
        <source srcSet={source.webp} type="image/webp" />
        <img src={source.png} width={source.width} height={source.height} alt="GreyGuard" />
      </picture>
    </span>
  )
}
