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
