import {describe,expect,it} from "vitest"
import {removalProgress} from "../pages/CapabilityRemovalPage"
describe("capability removal",()=>{
 it("reports ordered verification progress",()=>expect(removalProgress([{status:"COMPLETED"},{status:"PENDING"}])).toEqual({completed:1,total:2}))
 it("does not count pending evidence as complete",()=>expect(removalProgress([{status:"PENDING"},{status:"PENDING"}]).completed).toBe(0))
})
