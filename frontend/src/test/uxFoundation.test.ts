import {describe,expect,it} from "vitest"
import {normalizeToastDuration} from "../context/ToastContext"
describe("Shared UX foundation",()=>{it("uses a readable default toast duration",()=>expect(normalizeToastDuration()).toBe(5000));it("prevents disappearing too quickly",()=>expect(normalizeToastDuration(200)).toBe(2000));it("caps excessively long messages",()=>expect(normalizeToastDuration(60000)).toBe(15000))})
