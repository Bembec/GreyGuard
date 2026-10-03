import { describe, expect, it } from "vitest"
import { safeBundleFilename } from "../pages/RequestDetailPage"
describe("Request investigation", () => {
  it("creates a safe export filename", () => expect(safeBundleFilename("req/unsafe:1")).toBe("greyguard-request-req-unsafe-1.json"))
})
