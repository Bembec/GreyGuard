import {
  Ban,
  Box,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  File,
  FileText,
  Folder,
  LockKeyhole,
  Network,
  RefreshCw,
  ShieldCheck,
  TerminalSquare,
  Wrench,
} from "lucide-react";
import {
  useMemo,
  useState,
} from "react";
import { useQuery } from "@tanstack/react-query";

import { ErrorState, LoadingState } from "../components/AsyncState";
import "../styles/sandbox.css";


type ToolResponse = {
  tools: string[];
  sandbox_only: boolean;
  network_access: boolean;
  arbitrary_command_execution: boolean;
  absolute_paths_allowed: boolean;
  path_escape_allowed: boolean;
};

type SandboxEntry = {
  name: string;
  path: string;
  type: string;
  size_bytes: number | null;
};

type SandboxResponse = {
  initialized: boolean;
  sandbox_name: string;
  controls: {
    sandbox_only: boolean;
    network_access: boolean;
    arbitrary_command_execution: boolean;
    absolute_paths_allowed: boolean;
    path_escape_allowed: boolean;
  };
  resources: {
    success: boolean;
    tool: string;
    target: string;
    message: string;
    data: {
      entries: SandboxEntry[];
      entry_count: number;
    };
  };
};

type ToolRequest = {
  request_id: string;
  agent_name: string;
  timestamp: string;
  updated_at: string;
  action: string;
  target: string;
  dry_run: boolean;
  policy_decision: string;
  approval_status: string;
  execution_status: string;
  risk_added: number;
  risk_score: number;
  result: Record<string, unknown> | null;
};

type ToolRequestResponse = {
  requests: ToolRequest[];
  count: number;
};

type ApiError = {
  detail?: string;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "/api";

const toolDescriptions: Record<string, string> = {
  list_files:
    "Lists metadata for files contained inside an approved sandbox directory.",
  read_file:
    "Reads a validated UTF-8 text file without permitting access outside the sandbox.",
  search_logs:
    "Searches approved local log evidence using a controlled query.",
  write_note:
    "Writes a text note only inside the dedicated sandbox notes directory after approval.",
};

function adminHeaders() {
  const pin = sessionStorage.getItem(
    "greyguard_admin_pin",
  );

  if (!pin) {
    throw new Error(
      "Administrator session is missing.",
    );
  }

  return {
    "Content-Type": "application/json",
    "X-Admin-Pin": pin,
  };
}

async function readResponse<T>(
  response: Response,
): Promise<T> {
  const data = (await response.json().catch(
    () => ({}),
  )) as T & ApiError;

  if (!response.ok) {
    throw new Error(
      data.detail
      ?? `Request failed with status ${response.status}.`,
    );
  }

  return data;
}

async function fetchTools() {
  const response = await fetch(
    `${API_BASE_URL}/tools`,
  );

  return readResponse<ToolResponse>(response);
}

async function fetchSandbox() {
  const response = await fetch(
    `${API_BASE_URL}/sandbox/resources`,
    {
      headers: adminHeaders(),
    },
  );

  return readResponse<SandboxResponse>(response);
}

async function fetchToolRequests() {
  const response = await fetch(
    `${API_BASE_URL}/tool-requests?limit=20`,
    {
      headers: adminHeaders(),
    },
  );

  return readResponse<ToolRequestResponse>(
    response,
  );
}

function formatTimestamp(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}

function executionClass(status: string) {
  const normalized = status.toLowerCase();

  if (
    normalized === "succeeded"
    || normalized === "dry_run"
  ) {
    return "sandbox-status success";
  }

  if (
    normalized === "failed"
    || normalized === "denied"
    || normalized === "blocked"
  ) {
    return "sandbox-status danger";
  }

  return "sandbox-status pending";
}

export default function SandboxPage() {
  const [expandedRequest, setExpandedRequest] =
    useState<string | null>(null);

  const toolsQuery = useQuery({
    queryKey: ["controlled-tools"],
    queryFn: fetchTools,
  });

  const sandboxQuery = useQuery({
    queryKey: ["sandbox-resources"],
    queryFn: fetchSandbox,
    refetchInterval: 15000,
  });

  const requestsQuery = useQuery({
    queryKey: ["tool-requests", "sandbox"],
    queryFn: fetchToolRequests,
    refetchInterval: 15000,
  });

  const tools = toolsQuery.data?.tools ?? [];
  const entries =
    sandboxQuery.data?.resources.data.entries
    ?? [];
  const requests =
    requestsQuery.data?.requests ?? [];

  const executionStats = useMemo(() => ({
    succeeded: requests.filter(
      (request) =>
        request.execution_status === "SUCCEEDED",
    ).length,
    dryRuns: requests.filter(
      (request) =>
        request.execution_status === "DRY_RUN",
    ).length,
    failed: requests.filter(
      (request) =>
        request.execution_status === "FAILED",
    ).length,
  }), [requests]);

  const loading =
    toolsQuery.isLoading
    || sandboxQuery.isLoading
    || requestsQuery.isLoading;

  const error =
    toolsQuery.error
    ?? sandboxQuery.error
    ?? requestsQuery.error;

  if (loading) {
    return (
      <main className="sandbox-page sandbox-centered">
        <LoadingState label="Inspecting the containment boundary" rows={5} />
      </main>
    );
  }

  if (error) {
    return (
      <main className="sandbox-page sandbox-centered">
        <ErrorState message={error instanceof Error ? error.message : "GreyGuard could not load sandbox data."} onRetry={() => { void toolsQuery.refetch(); void sandboxQuery.refetch(); void requestsQuery.refetch(); }} />
      </main>
    );
  }

  return (
    <main className="sandbox-page">
      <div className="sandbox-vault" />
      <div className="sandbox-grid" />
      <div className="sandbox-glow" />

      <header className="sandbox-hero">
        <div>
          <span>Contained execution</span>
          <h1>Controlled Sandbox</h1>
          <p>
            Inspect GreyGuard’s restricted filesystem,
            approved tool surface and persistent
            execution evidence without exposing the
            host laptop.
          </p>
        </div>

        <div className="sandbox-seal">
          <LockKeyhole />
          <div>
            <strong>Boundary sealed</strong>
            <small>
              Local sandbox · network disabled
            </small>
          </div>
        </div>
      </header>

      <section className="sandbox-stat-grid">
        <article>
          <Wrench />
          <div>
            <span>Controlled tools</span>
            <strong>{tools.length}</strong>
            <small>Explicit allowlist</small>
          </div>
        </article>

        <article>
          <FileText />
          <div>
            <span>Sandbox resources</span>
            <strong>{entries.length}</strong>
            <small>Files and directories</small>
          </div>
        </article>

        <article>
          <CheckCircle2 />
          <div>
            <span>Successful executions</span>
            <strong>
              {executionStats.succeeded}
            </strong>
            <small>Approved operations</small>
          </div>
        </article>

        <article>
          <ShieldCheck />
          <div>
            <span>Safety validations</span>
            <strong>
              {executionStats.dryRuns
                + executionStats.failed}
            </strong>
            <small>Dry runs and blocked escapes</small>
          </div>
        </article>
      </section>

      <section className="sandbox-layout">
        <div className="sandbox-main-column">
          <article className="sandbox-panel">
            <div className="sandbox-panel-heading">
              <div>
                <span>Tool gateway</span>
                <h2>Approved capabilities</h2>
              </div>
              <TerminalSquare />
            </div>

            <div className="sandbox-tool-grid">
              {tools.map((tool) => (
                <div
                  className="sandbox-tool-card"
                  key={tool}
                >
                  <div>
                    <Wrench />
                  </div>
                  <strong>{tool}</strong>
                  <p>
                    {toolDescriptions[tool]
                      ?? "Controlled GreyGuard capability."}
                  </p>
                  <span>
                    Policy and scope enforced
                  </span>
                </div>
              ))}
            </div>
          </article>

          <article className="sandbox-panel">
            <div className="sandbox-panel-heading">
              <div>
                <span>Execution evidence</span>
                <h2>Recent controlled requests</h2>
              </div>

              <button
                type="button"
                className="sandbox-refresh"
                onClick={() =>
                  void requestsQuery.refetch()
                }
              >
                <RefreshCw />
                Refresh
              </button>
            </div>

            <div className="sandbox-request-list">
              {requests.map((request) => {
                const expanded =
                  expandedRequest
                  === request.request_id;

                return (
                  <article
                    className="sandbox-request"
                    key={request.request_id}
                  >
                    <div className="sandbox-request-icon">
                      <TerminalSquare />
                    </div>

                    <div className="sandbox-request-main">
                      <div className="sandbox-request-top">
                        <div>
                          <strong>
                            {request.action}
                          </strong>
                          <span>
                            {request.agent_name}
                          </span>
                        </div>

                        <time>
                          {formatTimestamp(
                            request.timestamp,
                          )}
                        </time>
                      </div>

                      <div className="sandbox-request-meta">
                        <code>{request.target}</code>
                        <span
                          className={executionClass(
                            request.execution_status,
                          )}
                        >
                          {request.execution_status}
                        </span>
                        {request.dry_run && (
                          <span className="sandbox-dry-run">
                            DRY RUN
                          </span>
                        )}
                      </div>

                      {expanded && (
                        <div className="sandbox-evidence">
                          <div>
                            <span>Request ID</span>
                            <code>
                              {request.request_id}
                            </code>
                          </div>
                          <div>
                            <span>Policy decision</span>
                            <code>
                              {
                                request.policy_decision
                              }
                            </code>
                          </div>
                          <div>
                            <span>Approval</span>
                            <code>
                              {
                                request.approval_status
                              }
                            </code>
                          </div>
                          <div>
                            <span>Risk score</span>
                            <code>
                              {request.risk_score}
                            </code>
                          </div>
                          <div className="sandbox-result-json">
                            <span>Result evidence</span>
                            <pre>
                              {JSON.stringify(
                                request.result,
                                null,
                                2,
                              )}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      className="sandbox-expand"
                      onClick={() =>
                        setExpandedRequest(
                          expanded
                            ? null
                            : request.request_id,
                        )
                      }
                      aria-label={
                        expanded
                          ? "Collapse evidence"
                          : "Expand evidence"
                      }
                    >
                      {expanded
                        ? <ChevronUp />
                        : <ChevronDown />}
                    </button>
                  </article>
                );
              })}
            </div>
          </article>
        </div>

        <aside className="sandbox-side-column">
          <article className="sandbox-panel">
            <div className="sandbox-panel-heading">
              <div>
                <span>Filesystem boundary</span>
                <h2>Sandbox resources</h2>
              </div>
              <Box />
            </div>

            <div className="sandbox-resource-list">
              {entries.map((entry) => (
                <div
                  className="sandbox-resource"
                  key={entry.path}
                >
                  <div>
                    {entry.type === "DIRECTORY"
                      ? <Folder />
                      : <File />}
                  </div>

                  <div>
                    <strong>{entry.name}</strong>
                    <code>{entry.path}</code>
                  </div>

                  <span>
                    {entry.size_bytes === null
                      ? "DIR"
                      : `${entry.size_bytes} B`}
                  </span>
                </div>
              ))}
            </div>
          </article>

          <article className="sandbox-panel">
            <div className="sandbox-panel-heading">
              <div>
                <span>Containment posture</span>
                <h2>Security controls</h2>
              </div>
              <ShieldCheck />
            </div>

            <div className="sandbox-control-list">
              <div>
                <ShieldCheck />
                <span>Sandbox-only access</span>
                <strong>ENFORCED</strong>
              </div>

              <div>
                <Network />
                <span>External network</span>
                <strong>DISABLED</strong>
              </div>

              <div>
                <Ban />
                <span>Arbitrary commands</span>
                <strong>BLOCKED</strong>
              </div>

              <div>
                <Ban />
                <span>Absolute paths</span>
                <strong>BLOCKED</strong>
              </div>

              <div>
                <LockKeyhole />
                <span>Path traversal</span>
                <strong>BLOCKED</strong>
              </div>
            </div>
          </article>

          <article className="sandbox-panel sandbox-boundary-note">
            <LockKeyhole />
            <h2>Host separation</h2>
            <p>
              The gateway resolves every target against
              the sandbox root. A request such as
              <code>../README.md</code> fails before
              file access occurs.
            </p>
          </article>
        </aside>
      </section>
    </main>
  );
}
