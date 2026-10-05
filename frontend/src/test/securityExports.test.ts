import {describe,expect,it} from "vitest"
import {destinationHealth} from "../pages/SecurityExportsPage"

const base={destination_id:"dst_1",name:"SIEM",destination_type:"SPLUNK",endpoint:"https://example.com",enabled:true,minimization_profile:"STANDARD",rate_limit_per_minute:60,max_attempts:5,last_success_at:null,last_failure_at:null,last_error:null,credentials_stored:false}
describe("security export health",()=>{
 it("shows awaiting delivery before first result",()=>expect(destinationHealth(base)).toBe("AWAITING DELIVERY"))
 it("shows degraded when delivery failed",()=>expect(destinationHealth({...base,last_error:"timeout"})).toBe("DEGRADED"))
})
