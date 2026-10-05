import {describe,expect,it} from "vitest"
import {scheduleState} from "../pages/ReportGovernancePanel"
describe("report governance",()=>{
 it("labels enabled schedules as active",()=>expect(scheduleState(true)).toBe("ACTIVE"))
 it("labels disabled schedules",()=>expect(scheduleState(false)).toBe("DISABLED"))
})
