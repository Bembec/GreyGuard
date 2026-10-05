import {describe,expect,it} from "vitest"
import {deliveryState} from "../pages/CommunicationIntegrationsPage"
describe("communication integrations",()=>{it("labels disabled destinations",()=>expect(deliveryState(false)).toBe("DISABLED"));it("labels enabled destinations",()=>expect(deliveryState(true)).toBe("ENABLED"))})
