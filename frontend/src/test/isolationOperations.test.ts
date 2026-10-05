import {describe,expect,it} from "vitest"
import {workspaceState} from "../pages/IsolationOperationsPage"

describe("isolation operations",()=>{
  it("preserves active workspace state",()=>expect(workspaceState("ACTIVE")).toBe("ACTIVE"))
  it("treats closed workspaces as destroyed",()=>expect(workspaceState("CLOSED")).toBe("DESTROYED"))
})
