import {describe,expect,it} from "vitest"
import {adapterStateLabel} from "../pages/AgentAdaptersPage"

describe("agent adapter controls",()=>{
 it("shows enabled adapter state",()=>expect(adapterStateLabel(true)).toBe("Enabled"))
 it("shows the kill switch when disabled",()=>expect(adapterStateLabel(false)).toBe("Kill switch active"))
})
