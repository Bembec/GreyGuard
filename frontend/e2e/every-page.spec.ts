import {expect,test,type Page} from "@playwright/test"
import {navigationItems} from "../src/config/navigation"

// Signs in once as the platform administrator, then opens every page in the console.
// A page fails if it throws in the browser, shows an error state or triggers a server error.
test.describe.configure({mode:"serial"})

let page:Page
const pageErrors:string[]=[]
const serverErrors:string[]=[]

test.beforeAll(async({browser})=>{
 page=await browser.newPage()
 page.on("pageerror",error=>pageErrors.push(error.message))
 page.on("response",response=>{if(response.url().includes("/api/")&&response.status()>=500)serverErrors.push(`${response.status()} ${response.url()}`)})
 await page.goto("/")
 await page.locator("#admin-email").fill(process.env.GREYGUARD_E2E_EMAIL!)
 await page.locator("#admin-password").fill(process.env.GREYGUARD_E2E_PASSWORD!)
 await page.getByRole("button",{name:/Enter command center/i}).click()
 await expect(page.getByRole("heading",{level:1})).toBeVisible({timeout:20_000})
})

test.afterAll(async()=>{await page?.close()})

async function expectHealthyPage(path:string,heading?:string){
 pageErrors.length=0;serverErrors.length=0
 await page.goto(path)
 const title=page.getByRole("heading",{level:1})
 await expect(title).toBeVisible({timeout:15_000})
 if(heading)await expect(title).toHaveText(heading)
 await page.waitForLoadState("networkidle")
 await expect(page.getByText("Something went wrong"),"page shows an error state").toHaveCount(0)
 expect(pageErrors,"uncaught browser errors").toEqual([])
 expect(serverErrors,"API server errors").toEqual([])
}

for(const item of navigationItems){
 test(`${item.label} (${item.path}) loads without errors`,async()=>{await expectHealthyPage(item.path,item.label)})
}

test("unknown agent detail page fails gracefully",async()=>{await expectHealthyPage("/agents/no-such-agent")})
test("unknown request detail page fails gracefully",async()=>{await expectHealthyPage("/requests/no-such-request")})
