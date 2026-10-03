import {describe,expect,it} from "vitest"
import {enterprisePosture} from "../pages/EnterpriseIdentityPage"
describe("enterprise identity posture",()=>{it("surfaces emergency access first",()=>{expect(enterprisePosture({providers:1,workload_identities:2,pending_elevations:3,active_break_glass:1})).toBe("Emergency access active")});it("shows pending approval",()=>{expect(enterprisePosture({providers:1,workload_identities:0,pending_elevations:1,active_break_glass:0})).toBe("Approval required")})})
