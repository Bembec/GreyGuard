import {describe,expect,it} from "vitest"
import {responseTone} from "../pages/DefensiveIntegrationsPage"
describe("defensive integrations",()=>{
 it("shows pending approval distinctly",()=>expect(responseTone("PENDING_APPROVAL")).toBe("pending"))
 it("shows approved responses distinctly",()=>expect(responseTone("APPROVED")).toBe("approved"))
})
