import {describe,expect,it} from "vitest"
import {approvalLinkState} from "../pages/IncidentIntegrationsPage"
describe("approval link evidence",()=>{it("marks consumed links",()=>expect(approvalLinkState("2026-10-05","2099-01-01")).toBe("USED"));it("marks valid links active",()=>expect(approvalLinkState(null,"2099-01-01")).toBe("ACTIVE"))})
