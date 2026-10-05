import {describe,expect,it} from "vitest"
import {integrityLabel} from "../pages/AuditIntegrityPage"
describe("audit integrity status",()=>{it("labels verified chains",()=>expect(integrityLabel(1)).toBe("VERIFIED"));it("does not imply verification without evidence",()=>expect(integrityLabel(undefined)).toBe("NOT VERIFIED"))})
