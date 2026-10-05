import {describe,expect,it} from "vitest"
import {riskRank} from "../pages/ThreatRegisterPage"
describe("threat register",()=>{
 it("orders critical risk above high risk",()=>expect(riskRank("CRITICAL")).toBeGreaterThan(riskRank("HIGH")))
 it("orders low risk below medium risk",()=>expect(riskRank("LOW")).toBeLessThan(riskRank("MEDIUM")))
})
