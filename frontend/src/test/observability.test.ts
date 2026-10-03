import {describe,expect,it} from "vitest"
import {samplingPercent} from "../pages/ObservabilityPage"

describe("observability controls",()=>{
 it("formats fractional sampling",()=>expect(samplingPercent(.25)).toBe("25%"))
 it("formats disabled sampling",()=>expect(samplingPercent(0)).toBe("0%"))
})
