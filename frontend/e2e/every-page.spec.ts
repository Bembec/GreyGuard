import {expect,test,type Page} from "@playwright/test"
import {navigationItems} from "../src/config/navigation"

// Signs in once as the platform administrator, then opens every console page in its own tab
// with that session. A page fails if it throws in the browser, shows an error state or
// triggers an API server error. Each page passes or fails independently.

let session:Record<string,string>={}

test.beforeAll(async({browser})=>{
 // The first login on a fresh database also runs one-time initialization.
 test.setTimeout(120_000)
 const page=await browser.newPage()
 await page.goto("/")
 await page.locator("#admin-email").fill(process.env.GREYGUARD_E2E_EMAIL!)
 await page.locator("#admin-password").fill(process.env.GREYGUARD_E2E_PASSWORD!)
 const [login]=await Promise.all([
  page.waitForResponse(response=>response.url().endsWith("/auth/login")&&response.request().method()==="POST",{timeout:90_000}),
  page.getByRole("button",{name:/Enter command center/i}).click(),
 ])
 expect(login.status(),`login failed: ${await login.text()}`).toBe(200)
 // The login page also has a level-1 heading, so wait until the console has replaced it.
 await expect(page.getByRole("heading",{level:1})).not.toHaveText(/Every action passes/i,{timeout:30_000})
 session=await page.evaluate(()=>Object.fromEntries(Object.entries(sessionStorage)))
 await page.close()
})

async function expectHealthyPage(page:Page,path:string){
 const pageErrors:string[]=[],serverErrors:string[]=[]
 page.on("pageerror",error=>pageErrors.push(error.message))
 page.on("response",response=>{if(response.url().includes("/api/")&&response.status()>=500)serverErrors.push(`${response.status()} ${response.url()}`)})
 await page.addInitScript(values=>{for(const [key,value] of Object.entries(values))sessionStorage.setItem(key,value)},session)
 await page.goto(path)
 // Each page owns exactly one meaningful <h1> (enforced by this single-element locator); it must
 // have moved past the login tagline and must not be blank.
 const title=page.getByRole("heading",{level:1})
 await expect(title).not.toHaveText(/^\s*$|Every action passes/i,{timeout:15_000})
 // Pages with live streams never go fully idle, so settle for at most five seconds.
 await page.waitForLoadState("networkidle",{timeout:5_000}).catch(()=>undefined)
 await expect(page.getByText("Something went wrong"),"page shows an error state").toHaveCount(0)
 expect(pageErrors,"uncaught browser errors").toEqual([])
 expect(serverErrors,"API server errors").toEqual([])
}

for(const item of navigationItems){
 test(`${item.label} (${item.path}) loads without errors`,async({page})=>{await expectHealthyPage(page,item.path)})
}

test("unknown agent detail page fails gracefully",async({page})=>{await expectHealthyPage(page,"/agents/no-such-agent")})
test("unknown request detail page fails gracefully",async({page})=>{await expectHealthyPage(page,"/requests/no-such-request")})
test("settings shows the organization's plan and lifecycle from the real backend",async({page})=>{
 await expectHealthyPage(page,"/settings")
 await expect(page.getByRole("heading",{name:/Plan & usage/})).toBeVisible()
 await expect(page.getByRole("heading",{name:/Readiness & data/})).toBeVisible()
 await expect(page.getByText(/\d+ of 9 complete/)).toBeVisible({timeout:15_000})
 await expect(page.getByRole("button",{name:/Export organization data/})).toBeVisible()
})
test("an install operator assigns a plan from settings, and Dedicated needs contract limits",async({page})=>{
 await expectHealthyPage(page,"/settings")
 const form=page.locator("form.plan-assignment")
 await expect(form.getByRole("heading",{name:/assign plan/i})).toBeVisible({timeout:15_000})
 await expect(form.getByRole("option",{name:/TRANSITIONAL/i})).toHaveCount(0)
 await form.getByLabel("Plan").selectOption("DEDICATED")
 await expect(form.getByRole("button",{name:"Assign plan"})).toBeDisabled()
 await form.getByLabel("Plan").selectOption("FOUNDATION")
 await form.getByLabel("Status").selectOption("ACTIVE")
 const [assigned]=await Promise.all([
  page.waitForResponse(response=>/\/entitlements\/[^/]+$/.test(response.url())&&response.request().method()==="PUT"),
  form.getByRole("button",{name:"Assign plan"}).click(),
 ])
 expect(assigned.status(),await assigned.text()).toBe(200)
 await expect(page.getByRole("status").filter({hasText:/Assigned .*\(ACTIVE\)/})).toBeVisible()
})
test("the public status page works without signing in",async({page})=>{
 await page.goto("/status")
 await expect(page.getByRole("heading",{level:1,name:/service status/i})).toBeVisible()
 await expect(page.getByText("Control-plane API")).toBeVisible({timeout:15_000})
 await expect(page.getByText(/not a service outage/)).toBeVisible()
})
test("getting started shows the computed readiness steps",async({page})=>{
 await expectHealthyPage(page,"/getting-started")
 await expect(page.getByRole("heading",{name:"Readiness steps"})).toBeVisible({timeout:15_000})
 await expect(page.getByText(/steps complete|Ready for production/).first()).toBeVisible()
})
