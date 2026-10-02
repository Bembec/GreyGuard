import {describe,expect,it} from "vitest"
import {formatProtectionCategory} from "../pages/AbuseProtectionPage"
describe("Abuse-protection labels",()=>{it("formats policy categories for operators",()=>{expect(formatProtectionCategory("ADMIN_AUTH")).toBe("Admin Auth")});it("formats defensive event types",()=>{expect(formatProtectionCategory("RATE_LIMIT_EXCEEDED")).toBe("Rate Limit Exceeded")})})
