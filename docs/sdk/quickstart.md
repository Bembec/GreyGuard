# SDK Quick Start

## 1. Start GreyGuard

From the project root:

```powershell
python -m uvicorn backend.app.api:app --reload
```

The default examples connect to `http://127.0.0.1:8000`.

## 2. Configure an agent

Create or select an agent identity with only the scopes it needs. Store the
issued credential in your shell for the current session:

```powershell
$env:GREYGUARD_URL = "http://127.0.0.1:8000"
$env:GREYGUARD_AGENT_NAME = "your-agent-name"
$env:GREYGUARD_AGENT_KEY = Read-Host "Agent credential"
```

`Read-Host` avoids placing the credential directly in the command or example
source. Clear the variable when the session ends.

## 3. Install a client

Python:

```powershell
python -m pip install -e sdk\python
```

JavaScript/TypeScript:

```powershell
npm install .\sdk\javascript
```

## 4. Run a dry-run example

Python:

```powershell
python examples\sdk\python_dry_run.py
```

JavaScript:

```powershell
node examples\sdk\javascript-dry-run.mjs
```

Both examples submit `read_file` as a dry run. GreyGuard still authenticates
the identity, enforces the action scope, evaluates policy, records evidence,
and returns the request state without changing sandbox files.

## 5. Handle the result

- `ALLOW` can proceed through the controlled gateway.
- `ASK` waits for an authorized human decision.
- `BLOCK` must not be bypassed or retried as a different action.

Do not call policy evaluation as a preflight immediately before submission.
Submission already evaluates policy, and a second evaluation can update risk
state twice.
