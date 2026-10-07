import {defineConfig,devices} from "@playwright/test"
import {randomBytes} from "node:crypto"

// One random administrator password per run, shared by the isolated test backend and the tests.
process.env.GREYGUARD_E2E_EMAIL ??= "e2e-admin@example.com"
process.env.GREYGUARD_E2E_PASSWORD ??= randomBytes(24).toString("base64url")

export default defineConfig({
 testDir:"./e2e",fullyParallel:false,workers:1,retries:1,reporter:"list",
 use:{baseURL:"http://127.0.0.1:4173",trace:"retain-on-failure"},
 webServer:[
  // Never reuse a running backend: the tests must not write into a real database.
  {command:"python ../scripts/e2e_backend.py",url:"http://127.0.0.1:8000/health/live",reuseExistingServer:false,timeout:180_000,
   env:{GREYGUARD_BOOTSTRAP_EMAIL:process.env.GREYGUARD_E2E_EMAIL,GREYGUARD_BOOTSTRAP_PASSWORD:process.env.GREYGUARD_E2E_PASSWORD}},
  {command:"npm run preview -- --host 127.0.0.1",port:4173,reuseExistingServer:true},
 ],
 projects:[{name:"chromium",use:{...devices["Desktop Chrome"]}}],
})
