import generated from "../../config/brandAssets.generated.json"

/** A resolved brand asset. Generated from config/brand-assets.json by scripts/brand_assets.py. */
export interface BrandAsset {
  slot: string
  resolvedFrom: string
  path: string
  webp: string | null
  width: number | null
  height: number | null
  /** Internal only: the asset is the provisional artwork or a fallback. Never shown to visitors. */
  provisional: boolean
}

export type BrandSlot = keyof typeof generated.slots

/** The asset that renders for a slot. Replacing artwork changes the manifest, never this call. */
export function brandAsset(slot: BrandSlot): BrandAsset {
  return generated.slots[slot] as BrandAsset
}
