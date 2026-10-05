import {describe,expect,it} from "vitest"
import {simulationBanner} from "../pages/SimulationsPage"
describe("adversarial simulations",()=>{
 it("labels synthetic evidence explicitly",()=>expect(simulationBanner(true)).toBe("SIMULATION ONLY — NO REAL ACTION"))
 it("rejects non-simulated display records",()=>expect(simulationBanner(false)).toBe("INVALID RECORD"))
})
