import {
  AlertOctagon,
  Gauge,
  RefreshCw,
  RotateCcw,
  ShieldOff,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  useMemo,
  useRef,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ErrorState, LoadingState } from "../components/AsyncState";
import { useToast } from "../context/ToastContext";
import { useDismissableLayer } from "../hooks/useDismissableLayer";
import { usePermission } from "../hooks/usePermission";
import "../styles/risk-center.css";


type Agent = {
  agent_name: string;
  agent_status: string;
  risk_score: number;
  risk_level: string;
  blocked_attempts: number;
};

type PolicyResponse = {
  permissions: Record<string, string>;
  risk_weights: Record<string, number>;
  max_blocked_attempts: number;
  max_risk_score: number;
};

type ResetResponse = {
  agent_name: string;
  reset: boolean;
  message: string;
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
    "Content-Type": "application/json",
    "X-Admin-Pin": adminPin,
  };
}

async function fetchAgents(): Promise<Agent[]> {
  const response = await fetch(
    `${API_BASE_URL}/agents`,
    {
      headers: adminHeaders(),
    },
  );

  return readResponse<Agent[]>(response);
}

async function fetchPolicies(): Promise<PolicyResponse> {
  const response = await fetch(
    `${API_BASE_URL}/permissions`,
    {
      headers: adminHeaders(),
    },
  );

  return readResponse<PolicyResponse>(response);
}

async function resetAgent(
  agentName: string,
): Promise<ResetResponse> {
  const response = await fetch(
    `${API_BASE_URL}/agents/${encodeURIComponent(
      agentName,
    )}/reset`,
    {
      method: "POST",
      headers: adminHeaders(),
    },
  );

  return readResponse<ResetResponse>(response);
}

function riskClass(level: string) {
  return `risk-level risk-${level.toLowerCase()}`;
}

function riskColor(level: string) {
  switch (level.toUpperCase()) {
    case "CRITICAL":
      return "#ff4d6d";
    case "HIGH":
      return "#ff9f43";
    case "MEDIUM":
      return "#ffd166";
    default:
      return "#45e6b0";
  }
}

export default function RiskCenterPage() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();
  // POST /agents/{name}/reset requires identity:manage server-side (admin_auth.py's
  // required_permission) - only PLATFORM_ADMIN holds it. This page had no useAuth import at
  // all - the reset action (clears risk + reactivates a suspended agent) was gated only by
  // whether the agent was currently suspended, never by who was clicking it.
  const canResetAgents = usePermission({ permission: "identity:manage" });

  const [selectedAgent, setSelectedAgent] =
    useState<Agent | null>(null);
  const [simulationAction, setSimulationAction] =
    useState("");
  const [currentRisk, setCurrentRisk] =
    useState(0);

  const agentsQuery = useQuery({
    queryKey: ["agents", "risk-center"],
    queryFn: fetchAgents,
    refetchInterval: 10000,
  });

  const policiesQuery = useQuery({
    queryKey: ["permissions"],
    queryFn: fetchPolicies,
  });

  const resetMutation = useMutation({
    mutationFn: resetAgent,
    onSuccess: (result) => {
      pushToast({ tone: "success", title: "Agent security state reset", message: result.message });
      setSelectedAgent(null);
      void queryClient.invalidateQueries({
        queryKey: ["agents"],
      });
    },
    onError: (error: Error) => {
      pushToast({ tone: "error", title: "Could not reset agent", message: error.message });
    },
  });

  const resetCancelRef = useRef<HTMLButtonElement>(null);
  const resetDialogRef = useDismissableLayer<HTMLElement>({
    open: !!selectedAgent,
    onClose: () => setSelectedAgent(null),
    trapFocus: true,
    initialFocusRef: resetCancelRef,
    disabled: resetMutation.isPending,
    lockBodyScroll: true,
  });

  const agents = agentsQuery.data ?? [];
  const policy = policiesQuery.data;

  const rankedAgents = useMemo(
    () => [...agents].sort(
      (first, second) =>
        second.risk_score - first.risk_score,
    ),
    [agents],
  );

  const summary = useMemo(() => {
    const suspended = agents.filter(
      (agent) =>
        agent.agent_status === "SUSPENDED",
    ).length;

    const critical = agents.filter(
      (agent) =>
        agent.risk_level === "CRITICAL",
    ).length;

    const elevated = agents.filter(
      (agent) =>
        agent.risk_level === "HIGH"
        || agent.risk_level === "MEDIUM",
    ).length;

    const totalRisk = agents.reduce(
      (total, agent) =>
        total + agent.risk_score,
      0,
    );

    return {
      suspended,
      critical,
      elevated,
      averageRisk: agents.length
        ? Math.round(totalRisk / agents.length)
        : 0,
    };
  }, [agents]);

  const riskDistribution = useMemo(() => {
    const levels = [
      "LOW",
      "MEDIUM",
      "HIGH",
      "CRITICAL",
    ];

    return levels.map((level) => ({
      level,
      count: agents.filter(
        (agent) =>
          agent.risk_level === level,
      ).length,
    }));
  }, [agents]);

  const simulatedWeight =
    policy?.risk_weights[simulationAction] ?? 40;

  const projectedRisk =
    currentRisk + simulatedWeight;

  const projectedSuspension =
    projectedRisk
      >= (policy?.max_risk_score ?? 100);

  function confirmReset() {
    if (!selectedAgent) {
      return;
    }

    resetMutation.mutate(
      selectedAgent.agent_name,
    );
  }

  if (
    agentsQuery.isLoading
    || policiesQuery.isLoading
  ) {
    return (
      <main className="risk-center-page">
        <div className="risk-orbit" />
        <LoadingState label="Loading live risk intelligence" rows={5} />
      </main>
    );
  }

  if (
    agentsQuery.isError
    || policiesQuery.isError
  ) {
    const error =
      agentsQuery.error
      ?? policiesQuery.error;

    return (
      <main className="risk-center-page">
        <ErrorState message={error instanceof Error ? error.message : "GreyGuard could not load risk data."} onRetry={() => { void agentsQuery.refetch(); void policiesQuery.refetch(); }} />
      </main>
    );
  }

  return (
    <main className="risk-center-page">
      <div className="risk-grid-background" />
      <div className="risk-orbit risk-orbit-one" />
      <div className="risk-orbit risk-orbit-two" />

      <header className="risk-hero">
        <div>
          <span className="risk-eyebrow">
            Risk intelligence
          </span>
          <h1>Risk Center</h1>
          <p>
            Monitor accumulated agent risk,
            blocked attempts, suspension thresholds
            and administrative recovery.
          </p>
        </div>

        <div className="risk-live-status">
          <span />
          Live control-plane telemetry
        </div>
      </header>

      <section className="risk-summary-grid">
        <article className="risk-summary-card">
          <div className="risk-card-icon">
            <Users />
          </div>
          <div>
            <span>Monitored agents</span>
            <strong>{agents.length}</strong>
            <small>Independent identities</small>
          </div>
        </article>

        <article className="risk-summary-card">
          <div className="risk-card-icon warning">
            <TrendingUp />
          </div>
          <div>
            <span>Elevated risk</span>
            <strong>{summary.elevated}</strong>
            <small>Medium or high exposure</small>
          </div>
        </article>

        <article className="risk-summary-card">
          <div className="risk-card-icon danger">
            <AlertOctagon />
          </div>
          <div>
            <span>Critical agents</span>
            <strong>{summary.critical}</strong>
            <small>Immediate review required</small>
          </div>
        </article>

        <article className="risk-summary-card">
          <div className="risk-card-icon suspended">
            <ShieldOff />
          </div>
          <div>
            <span>Suspended</span>
            <strong>{summary.suspended}</strong>
            <small>Execution access refused</small>
          </div>
        </article>
      </section>

      <section className="risk-intelligence-grid">
        <article className="risk-panel risk-ranking-panel">
          <div className="risk-panel-header">
            <div>
              <span>Agent estate</span>
              <h2>Live risk ranking</h2>
            </div>

            <button
              className="risk-refresh-button"
              type="button"
              onClick={() =>
                void agentsQuery.refetch()
              }
            >
              <RefreshCw />
              Refresh
            </button>
          </div>

          <div className="risk-table-wrapper">
            <table className="risk-table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Risk level</th>
                  <th>Score</th>
                  <th>Blocked</th>
                  <th>Status</th>
                  <th>Control</th>
                </tr>
              </thead>
              <tbody>
                {rankedAgents.map((agent) => {
                  const maximum =
                    policy?.max_risk_score ?? 100;
                  const percentage = Math.min(
                    100,
                    Math.round(
                      (agent.risk_score / maximum)
                      * 100,
                    ),
                  );

                  return (
                    <tr key={agent.agent_name}>
                      <td>
                        <div className="risk-agent-name">
                          <span>
                            {agent.agent_name
                              .slice(0, 2)
                              .toUpperCase()}
                          </span>
                          <div>
                            <strong>
                              {agent.agent_name}
                            </strong>
                            <small>
                              Independent boundary
                            </small>
                          </div>
                        </div>
                      </td>

                      <td>
                        <span
                          className={riskClass(
                            agent.risk_level,
                          )}
                        >
                          {agent.risk_level}
                        </span>
                      </td>

                      <td>
                        <div className="risk-score-cell">
                          <div>
                            <strong>
                              {agent.risk_score}
                            </strong>
                            <small>
                              / {maximum}
                            </small>
                          </div>
                          <div className="risk-score-track">
                            <span
                              style={{
                                width: `${percentage}%`,
                                backgroundColor:
                                  riskColor(
                                    agent.risk_level,
                                  ),
                              }}
                            />
                          </div>
                        </div>
                      </td>

                      <td>
                        {agent.blocked_attempts}
                        {" / "}
                        {policy?.max_blocked_attempts
                          ?? 3}
                      </td>

                      <td>
                        <span
                          className={
                            agent.agent_status
                              === "SUSPENDED"
                              ? "risk-status suspended"
                              : "risk-status active"
                          }
                        >
                          {agent.agent_status}
                        </span>
                      </td>

                      <td>
                        {canResetAgents && (
                          <button
                            className="risk-row-action"
                            type="button"
                            disabled={
                              agent.agent_status
                              !== "SUSPENDED"
                            }
                            onClick={() =>
                              setSelectedAgent(agent)
                            }
                          >
                            <RotateCcw />
                            Reset
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </article>

        <aside className="risk-side-column">
          <article className="risk-panel">
            <div className="risk-panel-header">
              <div>
                <span>Estate posture</span>
                <h2>Risk distribution</h2>
              </div>
              <Gauge />
            </div>

            <div className="risk-distribution">
              {riskDistribution.map((item) => {
                const width = agents.length
                  ? Math.round(
                    (item.count / agents.length)
                    * 100,
                  )
                  : 0;

                return (
                  <div
                    className="risk-distribution-row"
                    key={item.level}
                  >
                    <div>
                      <span
                        style={{
                          backgroundColor:
                            riskColor(item.level),
                        }}
                      />
                      <strong>{item.level}</strong>
                      <small>{item.count}</small>
                    </div>

                    <div className="risk-distribution-track">
                      <span
                        style={{
                          width: `${width}%`,
                          backgroundColor:
                            riskColor(item.level),
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="risk-average">
              <span>Average estate risk</span>
              <strong>{summary.averageRisk}</strong>
            </div>
          </article>

          <article className="risk-panel risk-threshold-panel">
            <div className="risk-panel-header">
              <div>
                <span>Automatic enforcement</span>
                <h2>Suspension thresholds</h2>
              </div>
              <ShieldOff />
            </div>

            <div className="risk-threshold">
              <strong>
                {policy?.max_risk_score ?? 100}
              </strong>
              <span>Maximum risk score</span>
            </div>

            <div className="risk-threshold">
              <strong>
                {policy?.max_blocked_attempts ?? 3}
              </strong>
              <span>Maximum blocked attempts</span>
            </div>

            <p>
              Reaching either threshold suspends the
              affected agent independently. Other agents
              remain operational.
            </p>
          </article>
        </aside>
      </section>

      <section className="risk-panel risk-simulator">
        <div className="risk-panel-header">
          <div>
            <span>Preventive analysis</span>
            <h2>Risk projection simulator</h2>
          </div>
          <TrendingUp />
        </div>

        <p className="risk-simulator-copy">
          Preview an action’s effect without changing
          an agent, executing a tool, or writing an
          audit event.
        </p>

        <div className="risk-simulator-controls">
          <label>
            Current risk
            <input
              type="number"
              min="0"
              max="500"
              value={currentRisk}
              onChange={(event) =>
                setCurrentRisk(
                  Number(event.target.value),
                )
              }
            />
          </label>

          <label>
            Requested action
            <select
              value={simulationAction}
              onChange={(event) =>
                setSimulationAction(
                  event.target.value,
                )
              }
            >
              <option value="">
                Unknown action
              </option>
              {Object.keys(
                policy?.permissions ?? {},
              ).map((action) => (
                <option
                  value={action}
                  key={action}
                >
                  {action}
                </option>
              ))}
            </select>
          </label>

          <div className="risk-projection-result">
            <div>
              <span>Risk added</span>
              <strong>+{simulatedWeight}</strong>
            </div>
            <div>
              <span>Projected score</span>
              <strong>{projectedRisk}</strong>
            </div>
            <div>
              <span>Outcome</span>
              <strong
                className={
                  projectedSuspension
                    ? "projection-danger"
                    : "projection-safe"
                }
              >
                {projectedSuspension
                  ? "SUSPEND"
                  : "CONTINUE"}
              </strong>
            </div>
          </div>
        </div>
      </section>

      {selectedAgent && (
        <div
          className="risk-modal-backdrop"
          role="presentation"
          onMouseDown={() =>
            setSelectedAgent(null)
          }
        >
          <section
            ref={resetDialogRef}
            className="risk-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="risk-reset-title"
            onMouseDown={(event) =>
              event.stopPropagation()
            }
          >
            <div className="risk-modal-icon">
              <RotateCcw />
            </div>

            <span>Administrative recovery</span>
            <h2 id="risk-reset-title">
              Reset {selectedAgent.agent_name}?
            </h2>

            <p>
              This will reactivate the agent and reset
              its accumulated risk score and blocked
              attempts. The reset will remain visible
              in GreyGuard’s audit evidence.
            </p>

            <div className="risk-reset-summary">
              <div>
                <span>Current risk</span>
                <strong>
                  {selectedAgent.risk_score}
                </strong>
              </div>
              <div>
                <span>Blocked attempts</span>
                <strong>
                  {selectedAgent.blocked_attempts}
                </strong>
              </div>
            </div>

            <div className="risk-modal-actions">
              <button
                ref={resetCancelRef}
                type="button"
                className="secondary"
                onClick={() =>
                  setSelectedAgent(null)
                }
              >
                Cancel
              </button>

              <button
                type="button"
                className="primary"
                disabled={resetMutation.isPending}
                onClick={confirmReset}
              >
                {resetMutation.isPending
                  ? "Resetting…"
                  : "Confirm secure reset"}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
