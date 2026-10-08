import {expect,test} from "@playwright/test"

// Confirms the production build actually wires up the web app manifest and service worker
// (see vite.config.ts's VitePWA config) rather than just trusting the build log's own report.

test("the app shell links a valid web app manifest",async({page,baseURL})=>{
 await page.goto("/")
 const manifestHref=await page.locator('link[rel="manifest"]').getAttribute("href")
 expect(manifestHref).toBeTruthy()
 const response=await page.request.get(new URL(manifestHref!,baseURL).toString())
 expect(response.ok()).toBe(true)
 const manifest=await response.json()
 expect(manifest.name).toMatch(/GreyGuard/)
 expect(Array.isArray(manifest.icons)&&manifest.icons.length).toBeGreaterThan(0)
})

test("the generated service worker is reachable and precaches the app shell, never the API",async({page,baseURL})=>{
 await page.goto("/")
 const response=await page.request.get(new URL("/sw.js",baseURL).toString())
 expect(response.ok()).toBe(true)
 const body=await response.text()
 expect(body).not.toContain("/api/")
})
