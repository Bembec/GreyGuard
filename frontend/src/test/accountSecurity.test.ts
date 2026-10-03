import {describe,expect,it} from "vitest"
import {sessionState} from "../pages/AccountSecurityPage"
describe("account security",()=>{it("shows revoked sessions",()=>expect(sessionState({session_id:"1",created_at:"",expires_at:"",revoked_at:"now",device_name:null,ip_address:null,last_seen_at:null})).toBe("Revoked"));it("shows active sessions",()=>expect(sessionState({session_id:"1",created_at:"",expires_at:"2999-01-01T00:00:00Z",revoked_at:null,device_name:null,ip_address:null,last_seen_at:null})).toBe("Active"))})
