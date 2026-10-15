import {expect,test} from "@playwright/test"

test("unauthenticated users see the administrator login boundary",async({page})=>{
 await page.goto("/")
 await expect(page.getByRole("heading",{name:/Every action passes/i})).toBeVisible()
 await expect(page.locator('input[type="password"]')).toBeVisible()
})

test("unknown routes do not expose protected content",async({page})=>{
 await page.goto("/definitely-not-a-greyguard-route")
 await expect(page.getByRole("heading",{name:/Every action passes/i})).toBeVisible()
})
test("the built app serves an unexpired RFC 9116 security.txt naming the private advisory channel",async({request})=>{
 const response=await request.get("/.well-known/security.txt")
 expect(response.status()).toBe(200)
 expect(response.headers()["content-type"]).toContain("text/plain")
 const body=await response.text()
 expect(body).toContain("Contact: https://github.com/Bembec/GreyGuard/security/advisories/new")
 expect(new Date(body.match(/^Expires: (.+)$/m)?.[1]??"").getTime()).toBeGreaterThan(Date.now())
})
