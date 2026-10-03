import { GreyGuardClient } from "../src/index.js"

const client = new GreyGuardClient({
  baseUrl: process.env.GREYGUARD_URL ?? "http://127.0.0.1:8000",
  agentName: process.env.GREYGUARD_AGENT_NAME,
  credential: process.env.GREYGUARD_AGENT_KEY,
  scopes: ["read_file"],
})

const result = await client.submit({
  action: "read_file",
  target: "public_report.txt",
})

console.log(`request=${result.request_id} status=${result.execution_status}`)
