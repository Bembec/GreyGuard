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

async function expectHealthyPage(page:Page,path:string,heading?:string){
 const pageErrors:string[]=[],serverErrors:string[]=[]
 page.on("pageerror",error=>pageErrors.push(error.message))
 page.on("response",response=>{if(response.url().includes("/api/")&&response.status()>=500)serverErrors.push(`${response.status()} ${response.url()}`)})
 await page.addInitScript(values=>{for(const [key,value] of Object.entries(values))sessionStorage.setItem(key,value)},session)
 await page.goto(path)
 const title=page.getByRole("heading",{level:1})
 await expect(title).not.toHaveText(/Every action passes/i,{timeout:15_000})
 if(heading)await expect(title).toHaveText(heading)
 // Pages with live streams never go fully idle, so settle for at most five seconds.
 await page.waitForLoadState("networkidle",{timeout:5_000}).catch(()=>undefined)
 await expect(page.getByText("Something went wrong"),"page shows an error state").toHaveCount(0)
 expect(pageErrors,"uncaught browser errors").toEqual([])
 expect(serverErrors,"API server errors").toEqual([])
}

for(const item of navigationItems){
 test(`${item.label} (${item.path}) loads without errors`,async({page})=>{await expectHealthyPage(page,item.path,item.label)})
}

test("unknown agent detail page fails gracefully",async({page})=>{await expectHealthyPage(page,"/agents/no-such-agent")})
test("unknown request detail page fails gracefully",async({page})=>{await expectHealthyPage(page,"/requests/no-such-request")})
