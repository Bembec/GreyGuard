import {describe,expect,it} from "vitest"
import {isolationState} from "../pages/ExecutionIsolationPage"
describe("execution isolation",()=>{it("shows disabled by default",()=>expect(isolationState(false)).toBe("DISABLED"));it("shows explicit enablement",()=>expect(isolationState(true)).toBe("ENABLED"))})
