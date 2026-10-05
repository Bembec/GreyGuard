import {describe,expect,it} from "vitest"
import {telemetryState} from "../pages/EndpointTelemetryPage"
describe("endpoint telemetry",()=>{
 it("is visibly disabled before enablement",()=>expect(telemetryState(false)).toBe("DISABLED"))
 it("labels enabled collection visibly",()=>expect(telemetryState(true)).toBe("MONITORING"))
})
