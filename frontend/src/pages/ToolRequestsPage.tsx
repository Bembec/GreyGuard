import {
  Activity,
  Check,
  ChevronRight,
  Clipboard,
  Clock3,
  Code2,
  FileSearch,
  Filter,
  RefreshCw,
  Route,
  Search,
  ShieldAlert,
  ShieldCheck,
  TerminalSquare,
  X,
  Zap,
} from "lucide-react";
import {
  useMemo,
  useState,
} from "react";
import {
  useQuery,
} from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/AsyncState";
import "../styles/requests.css";


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
  executed_at: string | null;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
};

type ToolRequestResponse = {
  requests: ToolRequest[];
  count: number;
  filters: {
    agent_name: string | null;
    approval_status: string | null;
    execution_status: string | null;
    limit: number;
  };
};

type ApiError = {
  detail?: string;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "/api";

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

function adminHeaders() {
  const adminPin =
    sessionStorage.getItem("greyguard_admin_pin");

  if (!adminPin) {
    throw new Error(
      "Administrator session is missing. Sign in again.",
    );
  }

  return {
    "X-Admin-Pin": adminPin,
  };
}

async function fetchToolRequests():
Promise<ToolRequestResponse> {
  const response = await fetch(
    `${API_BASE_URL}/tool-requests?limit=200`,
    {
      headers: adminHeaders(),
    },
  );

  return readResponse<ToolRequestResponse>(
    response,
  );
}

function formatDate(value?: string | null) {
  if (!value) {
    return "Not recorded";
  }

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

function shortRequestId(requestId: string) {
  return requestId.slice(0, 8);
}

function statusClass(value: string) {
  return value
    .toLowerCase()
    .replaceAll("_", "-");
}

function readableStatus(value: string) {
  return value.replaceAll("_", " ");
}

function jsonText(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function executionDescription(
  request: ToolRequest,
) {
  switch (request.execution_status) {
    case "SUCCEEDED":
      return "The controlled tool completed successfully.";
    case "FAILED":
      return "Execution was attempted but containment or tool validation stopped it.";
    case "DRY_RUN":
      return "GreyGuard simulated the action without changing sandbox data.";
    case "DENIED":
      return "A human reviewer denied the sensitive request.";
    case "AWAITING_APPROVAL":
      return "Legacy request waiting for human authorization.";
    case "PENDING":
      return "Legacy request recorded before execution-state normalization.";
    case "NOT_STARTED":
      return "The request is authorized but has not started execution.";
    case "RUNNING":
      return "The controlled tool is currently executing.";
    default:
      return "Execution evidence is available for inspection.";
  }
}

export default function ToolRequestsPage() {
  const navigate = useNavigate();
  const [searchText, setSearchText] =
    useState("");
  const [decisionFilter, setDecisionFilter] =
    useState("ALL");
  const [executionFilter, setExecutionFilter] =
    useState("ALL");
  const [selectedRequestId, setSelectedRequestId] =
    useState<string | null>(null);
  const [copied, setCopied] =
    useState(false);

  const requestsQuery = useQuery({
    queryKey: ["tool-requests"],
    queryFn: fetchToolRequests,
    refetchInterval: 15_000,
  });

  const requests =
    requestsQuery.data?.requests ?? [];

  const selectedRequest = useMemo(
    () => requests.find(
      (request) =>
        request.request_id === selectedRequestId,
    ) ?? null,
    [requests, selectedRequestId],
  );

  const filteredRequests = useMemo(() => {
    const normalizedSearch =
      searchText.trim().toLowerCase();

    return requests.filter((request) => {
      const searchableText = [
        request.request_id,
        request.agent_name,
        request.action,
        request.target,
      ]
        .join(" ")
        .toLowerCase();

      const matchesSearch =
        !normalizedSearch
        || searchableText.includes(
          normalizedSearch,
        );

      const matchesDecision =
        decisionFilter === "ALL"
        || request.policy_decision
          === decisionFilter;

      const matchesExecution =
        executionFilter === "ALL"
        || request.execution_status
          === executionFilter;

      return (
        matchesSearch
        && matchesDecision
        && matchesExecution
      );
    });
  }, [
    requests,
    searchText,
    decisionFilter,
    executionFilter,
  ]);

  const succeededCount = requests.filter(
    (request) =>
      request.execution_status === "SUCCEEDED",
  ).length;

  const reviewCount = requests.filter(
    (request) =>
      request.approval_status === "PENDING"
      || request.execution_status
        === "AWAITING_APPROVAL",
  ).length;

  const containedCount = requests.filter(
    (request) =>
      request.execution_status === "FAILED"
      || request.execution_status === "DENIED",
  ).length;

  const dryRunCount = requests.filter(
    (request) =>
      request.execution_status === "DRY_RUN",
  ).length;

  async function copyRequestId() {
    if (!selectedRequest) {
      return;
    }

    await navigator.clipboard.writeText(
      selectedRequest.request_id,
    );

    setCopied(true);

    window.setTimeout(
      () => setCopied(false),
      1600,
    );
  }

  return (
    <main className="requests-page">
      <div
        className="requests-grid-background"
        aria-hidden="true"
      >
        <span className="request-flow flow-one" />
        <span className="request-flow flow-two" />
        <span className="request-flow flow-three" />
      </div>

      <section className="requests-heading">
        <div>
          <div className="requests-kicker">
            Controlled execution pipeline
          </div>

          <h1>
            Every action leaves evidence.
          </h1>

          <p>
            Follow agent requests from identity and
            policy evaluation through approval,
            sandbox execution, and final evidence.
          </p>
        </div>

        <button
          type="button"
          className="requests-refresh-button"
          onClick={() => requestsQuery.refetch()}
          disabled={requestsQuery.isFetching}
        >
          <RefreshCw
            size={17}
            className={
              requestsQuery.isFetching
                ? "spin"
                : undefined
            }
          />
          Refresh pipeline
        </button>
      </section>

      <section className="pipeline-strip">
        <div>
          <ShieldCheck size={18} />
          <span>Identity</span>
        </div>
        <ChevronRight size={15} />
        <div>
          <Route size={18} />
          <span>Policy</span>
        </div>
        <ChevronRight size={15} />
        <div>
          <Clock3 size={18} />
          <span>Approval</span>
        </div>
        <ChevronRight size={15} />
        <div>
          <TerminalSquare size={18} />
          <span>Execution</span>
        </div>
        <ChevronRight size={15} />
        <div>
          <FileSearch size={18} />
          <span>Evidence</span>
        </div>
      </section>

      <section className="request-stat-grid">
        <article className="request-stat-card cyan">
          <Activity size={21} />
          <span>Total requests</span>
          <strong>{requests.length}</strong>
          <small>
            Recorded controlled operations
          </small>
        </article>

        <article className="request-stat-card green">
          <Check size={21} />
          <span>Succeeded</span>
          <strong>{succeededCount}</strong>
          <small>
            Completed inside the gateway
          </small>
        </article>

        <article className="request-stat-card amber">
          <Clock3 size={21} />
          <span>Needs review</span>
          <strong>{reviewCount}</strong>
          <small>
            Pending human authorization
          </small>
        </article>

        <article className="request-stat-card red">
          <ShieldAlert size={21} />
          <span>Contained</span>
          <strong>{containedCount}</strong>
          <small>
            Failed safely or denied
          </small>
        </article>

        <article className="request-stat-card violet">
          <Zap size={21} />
          <span>Dry runs</span>
          <strong>{dryRunCount}</strong>
          <small>
            Simulated without side effects
          </small>
        </article>
      </section>

      <section className="requests-workspace">
        <div className="requests-list-panel">
          <div className="requests-toolbar">
            <label className="requests-search">
              <Search size={17} />

              <input
                type="search"
                value={searchText}
                onChange={(event) =>
                  setSearchText(event.target.value)
                }
                placeholder={
                  "Search agent, action, target or ID..."
                }
              />
            </label>

            <label className="requests-filter">
              <Filter size={15} />

              <select
                value={decisionFilter}
                onChange={(event) =>
                  setDecisionFilter(
                    event.target.value,
                  )
                }
              >
                <option value="ALL">
                  All decisions
                </option>
                <option value="ALLOW">
                  Allow
                </option>
                <option value="ASK">
                  Ask
                </option>
                <option value="BLOCK">
                  Block
                </option>
                <option value="REFUSED">
                  Refused
                </option>
              </select>
            </label>

            <label className="requests-filter">
              <Activity size={15} />

              <select
                value={executionFilter}
                onChange={(event) =>
                  setExecutionFilter(
                    event.target.value,
                  )
                }
              >
                <option value="ALL">
                  All execution states
                </option>
                <option value="SUCCEEDED">
                  Succeeded
                </option>
                <option value="FAILED">
                  Failed
                </option>
                <option value="DRY_RUN">
                  Dry run
                </option>
                <option value="DENIED">
                  Denied
                </option>
                <option value="NOT_STARTED">
                  Not started
                </option>
                <option value="RUNNING">
                  Running
                </option>
                <option value="PENDING">
                  Legacy pending
                </option>
                <option value="AWAITING_APPROVAL">
                  Legacy awaiting approval
                </option>
              </select>
            </label>
          </div>

          {requestsQuery.isLoading && (
            <LoadingState label="Loading request evidence" rows={5} />
          )}

          {requestsQuery.isError && (
            <ErrorState message={(requestsQuery.error as Error).message} onRetry={() => void requestsQuery.refetch()} />
          )}

          {!requestsQuery.isLoading
            && !requestsQuery.isError
            && (
              <div className="requests-table-wrapper">
                <table className="requests-table">
                  <thead>
                    <tr>
                      <th>Request</th>
                      <th>Agent and target</th>
                      <th>Policy</th>
                      <th>Approval</th>
                      <th>Execution</th>
                      <th>Risk</th>
                      <th aria-label="Inspect" />
                    </tr>
                  </thead>

                  <tbody>
                    {filteredRequests.map(
                      (request) => (
                        <tr
                          key={request.request_id}
                          className={
                            selectedRequestId
                              === request.request_id
                              ? "selected"
                              : undefined
                          }
                          onClick={() =>
                            setSelectedRequestId(
                              request.request_id,
                            )
                          }
                        >
                          <td>
                            <div className="request-id-cell">
                              <div className="request-action-icon">
                                <Code2 size={16} />
                              </div>

                              <div>
                                <strong>
                                  {request.action}
                                </strong>
                                <span>
                                  #
                                  {
                                    shortRequestId(
                                      request.request_id,
                                    )
                                  }
                                </span>
                              </div>
                            </div>
                          </td>

                          <td>
                            <div className="request-target-cell">
                              <strong>
                                {request.agent_name}
                              </strong>
                              <span title={request.target}>
                                {request.target}
                              </span>
                            </div>
                          </td>

                          <td>
                            <span
                              className={
                                `request-badge decision-${
                                  statusClass(
                                    request.policy_decision,
                                  )
                                }`
                              }
                            >
                              {
                                readableStatus(
                                  request.policy_decision,
                                )
                              }
                            </span>
                          </td>

                          <td>
                            <span
                              className={
                                `request-badge approval-${
                                  statusClass(
                                    request.approval_status,
                                  )
                                }`
                              }
                            >
                              {
                                readableStatus(
                                  request.approval_status,
                                )
                              }
                            </span>
                          </td>

                          <td>
                            <span
                              className={
                                `request-badge execution-${
                                  statusClass(
                                    request.execution_status,
                                  )
                                }`
                              }
                            >
                              {
                                readableStatus(
                                  request.execution_status,
                                )
                              }
                            </span>
                          </td>

                          <td>
                            <div className="request-risk">
                              <strong>
                                {request.risk_score}
                              </strong>
                              <span>
                                +{request.risk_added}
                              </span>
                            </div>
                          </td>

                          <td>
                            <button
                              type="button"
                              className="request-inspect-button"
                              onClick={(event) => {
                                event.stopPropagation();

                                navigate(`/requests/${encodeURIComponent(request.request_id)}`);
                              }}
                            >
                              Investigate
                            </button>
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>

                {filteredRequests.length === 0 && (
                  <div className="requests-empty">
                    <Search size={25} />
                    <strong>
                      No matching requests
                    </strong>
                    <span>
                      Change your search or filters.
                    </span>
                  </div>
                )}
              </div>
            )}
        </div>

        <aside className="request-detail-panel">
          {!selectedRequest ? (
            <div className="request-detail-empty">
              <div className="evidence-orbit">
                <FileSearch size={34} />
              </div>

              <strong>
                Select request evidence
              </strong>

              <p>
                Inspect the complete journey from
                agent identity to final controlled
                execution result.
              </p>
            </div>
          ) : (
            <>
              <div className="request-detail-header">
                <div>
                  <span>Request evidence</span>
                  <h2>
                    {selectedRequest.action}
                  </h2>
                </div>

                <button
                  type="button"
                  aria-label="Close request details"
                  onClick={() =>
                    setSelectedRequestId(null)
                  }
                >
                  <X size={18} />
                </button>
              </div>

              <button
                type="button"
                className="request-id-copy"
                onClick={copyRequestId}
              >
                <code>
                  {selectedRequest.request_id}
                </code>

                {copied ? (
                  <Check size={16} />
                ) : (
                  <Clipboard size={16} />
                )}
              </button>

              <div className="request-evidence-grid">
                <div>
                  <span>Agent</span>
                  <strong>
                    {selectedRequest.agent_name}
                  </strong>
                </div>

                <div>
                  <span>Target</span>
                  <strong>
                    {selectedRequest.target}
                  </strong>
                </div>

                <div>
                  <span>Risk score</span>
                  <strong>
                    {selectedRequest.risk_score}
                    {" "}
                    (+{selectedRequest.risk_added})
                  </strong>
                </div>

                <div>
                  <span>Mode</span>
                  <strong>
                    {selectedRequest.dry_run
                      ? "DRY RUN"
                      : "LIVE SANDBOX"}
                  </strong>
                </div>
              </div>

              <div className="request-timeline">
                <article>
                  <span className="timeline-node identity" />
                  <div>
                    <small>1 · Identity</small>
                    <strong>
                      {selectedRequest.agent_name}
                    </strong>
                    <p>
                      Authenticated agent submitted
                      the controlled request.
                    </p>
                  </div>
                </article>

                <article>
                  <span className="timeline-node policy" />
                  <div>
                    <small>2 · Policy decision</small>
                    <strong>
                      {
                        readableStatus(
                          selectedRequest
                            .policy_decision,
                        )
                      }
                    </strong>
                    <p>
                      GreyGuard evaluated action,
                      scope, state, and risk.
                    </p>
                  </div>
                </article>

                <article>
                  <span className="timeline-node approval" />
                  <div>
                    <small>3 · Approval</small>
                    <strong>
                      {
                        readableStatus(
                          selectedRequest
                            .approval_status,
                        )
                      }
                    </strong>
                    <p>
                      Human authority requirement
                      and outcome.
                    </p>
                  </div>
                </article>

                <article>
                  <span className="timeline-node execution" />
                  <div>
                    <small>4 · Execution</small>
                    <strong>
                      {
                        readableStatus(
                          selectedRequest
                            .execution_status,
                        )
                      }
                    </strong>
                    <p>
                      {
                        executionDescription(
                          selectedRequest,
                        )
                      }
                    </p>
                  </div>
                </article>
              </div>

              <div className="request-time-grid">
                <div>
                  <span>Requested</span>
                  <strong>
                    {formatDate(
                      selectedRequest.timestamp,
                    )}
                  </strong>
                </div>

                <div>
                  <span>Updated</span>
                  <strong>
                    {formatDate(
                      selectedRequest.updated_at,
                    )}
                  </strong>
                </div>

                <div>
                  <span>Executed</span>
                  <strong>
                    {formatDate(
                      selectedRequest.executed_at,
                    )}
                  </strong>
                </div>
              </div>

              <details className="request-json-block">
                <summary>Request payload</summary>
                <pre>
                  {jsonText(
                    selectedRequest.payload,
                  )}
                </pre>
              </details>

              <details
                className="request-json-block"
                open={
                  selectedRequest.result !== null
                }
              >
                <summary>Execution result</summary>
                <pre>
                  {selectedRequest.result
                    ? jsonText(
                      selectedRequest.result,
                    )
                    : "No result has been recorded."}
                </pre>
              </details>
            </>
          )}
        </aside>
      </section>
    </main>
  );
}
