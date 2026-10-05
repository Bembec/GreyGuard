import {describe,expect,it} from "vitest"
import {frontendAssuranceControls,hasAssuranceControl} from "../config/assurance"

describe("frontend assurance coverage",()=>{
  it("declares critical interface controls",()=>{
    expect(frontendAssuranceControls.length).toBeGreaterThanOrEqual(6)
    expect(hasAssuranceControl("authorization")).toBe(true)
    expect(hasAssuranceControl("execution isolation")).toBe(true)
  })
})
