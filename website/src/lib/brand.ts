import generated from "./brand-assets.generated.json"

export interface BrandAsset { path: string; webp: string | null; width: number | null; height: number | null; resolvedFrom: string; provisional: boolean }
export type BrandSlot = keyof typeof generated.slots

/** The asset for a slot, derived by `npm run brand` from config/brand-assets.json. */
export function brandAsset(slot: BrandSlot): BrandAsset {
  return generated.slots[slot] as BrandAsset
}
