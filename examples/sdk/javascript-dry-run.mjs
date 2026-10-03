import { GreyGuardClient } from "../../sdk/javascript/src/index.js"

function requiredEnvironment(name) {
  const value = process.env[name]
  if (!value) throw new Error(`Set ${name} before running this example.`)
  return value
}

const client = new GreyGuardClient({
  baseUrl: process.env.GREYGUARD_URL ?? "http://127.0.0.1:8000",
  agentName: requiredEnvironment("GREYGUARD_AGENT_NAME"),
  credential: requiredEnvironment("GREYGUARD_AGENT_KEY"),
  scopes: ["read_file"],
})

const result = await client.submit({
  action: "read_file",
  target: "public_report.txt",
  dryRun: true,
})

console.log(
  `request=${result.request_id} ` +
    `approval=${result.approval_status} ` +
    `execution=${result.execution_status}`,
)
