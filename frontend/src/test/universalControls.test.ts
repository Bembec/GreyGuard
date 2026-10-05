import {describe,expect,it} from "vitest"
import {controlState} from "../pages/UniversalControlsPage"
describe("universal controls",()=>{
 it("shows disabled capabilities",()=>expect(controlState({enabled:false,global_kill_switch:false,integration_kill_switch:false})).toBe("DISABLED"))
 it("prioritizes kill-switch state",()=>expect(controlState({enabled:true,global_kill_switch:true,integration_kill_switch:false})).toBe("KILLED"))
})
