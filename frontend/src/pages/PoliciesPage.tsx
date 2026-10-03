import {
  ArrowRight,
  Ban,
  CheckCircle2,
  CircleHelp,
  FileCode2,
  Gauge,
  GitBranch,
  LockKeyhole,
  Network,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import {
  useMemo,
  useState,
} from "react";
import {
  useQuery,
} from "@tanstack/react-query";

import { ErrorState, LoadingState } from "../components/AsyncState";
import "../styles/policies.css";
import PolicyGovernancePanel from "./PolicyGovernancePanel";


type PolicyDecision =
  | "ALLOW"
  | "ASK"
  | "BLOCK"
  | string;

type PolicyResponse = {
  policy_id: string | null;
  version_number: number | null;
  permissions: Record<string, PolicyDecision>;
  risk_weights: Record<string, number>;
  max_blocked_attempts: number;
  max_risk_score: number;
};

type PolicyRule = {
  action: string;
  decision: PolicyDecision;
  riskWeight: number;
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

async function fetchPolicies():
Promise<PolicyResponse> {
  const response = await fetch(
    `${API_BASE_URL}/permissions`,
  );

  return readResponse<PolicyResponse>(response);
}

function readableAction(action: string) {
  return action
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase(),
    );
}

function decisionExplanation(
  decision: PolicyDecision,
) {
  switch (decision) {
    case "ALLOW":
      return (
        "The request may proceed when the "
        + "authenticated identity also holds "
        + "the required action scope."
      );

    case "ASK":
      return (
        "Execution pauses until an authorized "
        + "human reviews and approves the request."
      );

    case "BLOCK":
      return (
        "The action is refused immediately and "
        + "its violation increases the agent's "
        + "security risk."
      );

    default:
      return (
        "Unknown decisions are treated "
        + "conservatively by GreyGuard."
      );
  }
}

function DecisionIcon({
  decision,
}: {
  decision: PolicyDecision;
}) {
  if (decision === "ALLOW") {
    return <CheckCircle2 size={17} />;
  }

  if (decision === "ASK") {
    return <CircleHelp size={17} />;
  }

  return <Ban size={17} />;
}

export default function PoliciesPage() {
  const [searchText, setSearchText] =
    useState("");
  const [decisionFilter, setDecisionFilter] =
    useState("ALL");
  const [simulatedAction, setSimulatedAction] =
    useState("");
  const [simulatedScoped, setSimulatedScoped] =
    useState(true);
  const [simulatedSuspended, setSimulatedSuspended] =
    useState(false);
  const [simulatedRisk, setSimulatedRisk] =
    useState(0);
  const [simulationRun, setSimulationRun] =
    useState(false);

  const policiesQuery = useQuery({
    queryKey: ["permissions"],
    queryFn: fetchPolicies,
    staleTime: 30_000,
  });

  const policy = policiesQuery.data;

  const rules = useMemo<PolicyRule[]>(
    () => {
      if (!policy) {
        return [];
      }

      return Object.entries(
        policy.permissions,
      )
        .map(([action, decision]) => ({
          action,
          decision,
          riskWeight:
            policy.risk_weights[action] ?? 0,
        }))
        .sort((first, second) =>
          first.action.localeCompare(
            second.action,
          ),
        );
    },
    [policy],
  );

  const filteredRules = useMemo(() => {
    const normalizedSearch =
      searchText.trim().toLowerCase();

    return rules.filter((rule) => {
      const matchesSearch =
        !normalizedSearch
        || rule.action
          .toLowerCase()
          .includes(normalizedSearch);

      const matchesDecision =
        decisionFilter === "ALL"
        || rule.decision === decisionFilter;

      return matchesSearch && matchesDecision;
    });
  }, [
    rules,
    searchText,
    decisionFilter,
  ]);

  const allowCount = rules.filter(
    (rule) => rule.decision === "ALLOW",
  ).length;

  const askCount = rules.filter(
    (rule) => rule.decision === "ASK",
  ).length;

  const blockCount = rules.filter(
    (rule) => rule.decision === "BLOCK",
  ).length;

  const highestRiskRule = [...rules].sort(
    (first, second) =>
      second.riskWeight - first.riskWeight,
  )[0];

  const selectedRule = rules.find(
    (rule) =>
      rule.action === simulatedAction,
  );

  function simulationResult() {
    if (!policy) {
      return null;
    }

    if (simulatedSuspended) {
      return {
        decision: "REFUSED",
        title: "Agent suspended",
        message: (
          "Suspended agents cannot execute even "
          + "normally allowed actions until an "
          + "administrator resets their state."
        ),
        projectedRisk: simulatedRisk,
      };
    }

    if (!selectedRule) {
      return {
        decision: "BLOCK",
        title: "Unknown action",
        message: (
          "Actions absent from the active policy "
          + "default to BLOCK."
        ),
        projectedRisk: Math.min(
          simulatedRisk + 40,
          999,
        ),
      };
    }

    if (!simulatedScoped) {
      return {
        decision: "REFUSED",
        title: "Scope boundary denied",
        message: (
          "Agent identity is valid, but the "
          + "credential does not include the "
          + `required ${selectedRule.action} scope.`
        ),
        projectedRisk: simulatedRisk,
      };
    }

    const projectedRisk =
      simulatedRisk
      + selectedRule.riskWeight;

    if (
      projectedRisk
      >= policy.max_risk_score
    ) {
      return {
        decision: "REFUSED",
        title: "Suspension threshold reached",
        message: (
          "The action's risk would raise the "
          + "agent to GreyGuard's automatic "
          + "suspension threshold."
        ),
        projectedRisk,
      };
    }

    return {
      decision: selectedRule.decision,
      title:
        selectedRule.decision === "ALLOW"
          ? "Policy permits execution"
          : (
            selectedRule.decision === "ASK"
              ? "Human approval required"
              : "Policy blocks execution"
          ),
      message: decisionExplanation(
        selectedRule.decision,
      ),
      projectedRisk,
    };
  }

  const result =
    simulationRun
      ? simulationResult()
      : null;

  return (
    <main className="policies-page">
      <div
        className="policy-network-background"
        aria-hidden="true"
      >
        <span className="policy-node node-one" />
        <span className="policy-node node-two" />
        <span className="policy-node node-three" />
        <span className="policy-node node-four" />
        <span className="policy-link link-one" />
        <span className="policy-link link-two" />
        <span className="policy-link link-three" />
        <Network size={230} />
      </div>

      <section className="policies-heading">
        <div>
          <div className="policies-kicker">
            Active enforcement policy
          </div>

          <h1>
            Identity never implies permission.
          </h1>

          <p>
            GreyGuard evaluates agent state, scope,
            requested action, policy decision, human
            authority, and accumulated risk before
            controlled execution can occur.
          </p>
        </div>

        <button
          type="button"
          className="policies-refresh-button"
          onClick={() => policiesQuery.refetch()}
          disabled={policiesQuery.isFetching}
        >
          <RefreshCw
            size={17}
            className={
              policiesQuery.isFetching
                ? "spin"
                : undefined
            }
          />
          Refresh policy
        </button>
      </section>

      <section className="policy-flow">
        <div>
          <LockKeyhole size={18} />
          <span>Identity</span>
        </div>

        <ArrowRight size={15} />

        <div>
          <FileCode2 size={18} />
          <span>Scope</span>
        </div>

        <ArrowRight size={15} />

        <div>
          <GitBranch size={18} />
          <span>Policy</span>
        </div>

        <ArrowRight size={15} />

        <div>
          <Gauge size={18} />
          <span>Risk</span>
        </div>

        <ArrowRight size={15} />

        <div>
          <ShieldCheck size={18} />
          <span>Decision</span>
        </div>
      </section>

      {policiesQuery.isLoading && (
        <LoadingState label="Loading active policy" rows={4} />
      )}

      {policiesQuery.isError && (
        <ErrorState message={(policiesQuery.error as Error).message} onRetry={() => void policiesQuery.refetch()} />
      )}

      {policy && (
        <>
          <section className="policy-stat-grid">
            <article className="policy-stat-card green">
              <CheckCircle2 size={22} />
              <span>Allowed actions</span>
              <strong>{allowCount}</strong>
              <small>
                Scoped low-friction operations
              </small>
            </article>

            <article className="policy-stat-card amber">
              <CircleHelp size={22} />
              <span>Approval actions</span>
              <strong>{askCount}</strong>
              <small>
                Human authorization required
              </small>
            </article>

            <article className="policy-stat-card red">
              <Ban size={22} />
              <span>Blocked actions</span>
              <strong>{blockCount}</strong>
              <small>
                Immediately refused by policy
              </small>
            </article>

            <article className="policy-stat-card violet">
              <Gauge size={22} />
              <span>Risk threshold</span>
              <strong>
                {policy.max_risk_score}
              </strong>
              <small>
                Automatic suspension boundary
              </small>
            </article>

            <article className="policy-stat-card cyan">
              <ShieldAlert size={22} />
              <span>Block threshold</span>
              <strong>
                {policy.max_blocked_attempts}
              </strong>
              <small>
                Attempts before suspension
              </small>
            </article>
          </section>

          <section className="policy-workspace">
            <div className="policy-matrix-panel">
              <div className="policy-panel-header">
                <div>
                  <span>Decision matrix</span>
                  <h2>Active action rules</h2>
                </div>

                <div className="policy-version">
                  <span>ACTIVE</span>
                  <strong>Core Policy V{policy.version_number ?? "—"}</strong>
                </div>
              </div>

              <div className="policy-toolbar">
                <label className="policy-search">
                  <Search size={16} />

                  <input
                    type="search"
                    value={searchText}
                    onChange={(event) =>
                      setSearchText(
                        event.target.value,
                      )
                    }
                    placeholder="Search action..."
                  />
                </label>

                <label className="policy-filter">
                  <SlidersHorizontal size={16} />

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
                  </select>
                </label>
              </div>

              <div className="policy-rule-list">
                {filteredRules.map((rule) => (
                  <article
                    key={rule.action}
                    className={
                      `policy-rule ${
                        rule.decision.toLowerCase()
                      }`
                    }
                  >
                    <div
                      className="policy-rule-icon"
                    >
                      <DecisionIcon
                        decision={rule.decision}
                      />
                    </div>

                    <div className="policy-rule-name">
                      <strong>
                        {readableAction(
                          rule.action,
                        )}
                      </strong>
                      <code>{rule.action}</code>
                    </div>

                    <span
                      className={
                        `policy-decision ${
                          rule.decision
                            .toLowerCase()
                        }`
                      }
                    >
                      {rule.decision}
                    </span>

                    <div className="policy-risk-weight">
                      <span>Risk weight</span>
                      <strong>
                        +{rule.riskWeight}
                      </strong>
                    </div>

                    <p>
                      {
                        decisionExplanation(
                          rule.decision,
                        )
                      }
                    </p>
                  </article>
                ))}

                {filteredRules.length === 0 && (
                  <div className="policy-empty">
                    <Search size={24} />
                    <strong>
                      No matching policy rules
                    </strong>
                    <span>
                      Change the search or decision
                      filter.
                    </span>
                  </div>
                )}
              </div>
            </div>

            <aside className="policy-insight-panel">
              <div className="policy-insight-header">
                <span>Enforcement intelligence</span>
                <h2>Policy posture</h2>
              </div>

              <div className="policy-posture-ring">
                <div>
                  <strong>{rules.length}</strong>
                  <span>rules</span>
                </div>
              </div>

              <div className="policy-posture-list">
                <div>
                  <span>
                    Default unknown action
                  </span>
                  <strong className="blocked">
                    BLOCK
                  </strong>
                </div>

                <div>
                  <span>
                    Suspended agent action
                  </span>
                  <strong className="refused">
                    REFUSED
                  </strong>
                </div>

                <div>
                  <span>
                    Missing credential scope
                  </span>
                  <strong className="refused">
                    REFUSED
                  </strong>
                </div>

                <div>
                  <span>
                    Highest action risk
                  </span>
                  <strong>
                    {
                      highestRiskRule
                        ? (
                          `${readableAction(
                            highestRiskRule.action,
                          )} +${
                            highestRiskRule.riskWeight
                          }`
                        )
                        : "None"
                    }
                  </strong>
                </div>
              </div>

              <div className="policy-principle">
                <ShieldCheck size={20} />
                <div>
                  <strong>
                    Core security principle
                  </strong>
                  <p>
                    Agent identity proves who is
                    requesting. Permission determines
                    what that identity may do.
                  </p>
                </div>
              </div>
            </aside>
          </section>

          <PolicyGovernancePanel />

          <section className="policy-simulator">
            <div className="simulator-heading">
              <div>
                <span>Safe deterministic preview</span>
                <h2>Policy decision simulator</h2>
                <p>
                  Preview policy logic without
                  executing a tool or changing any
                  agent state.
                </p>
              </div>

              <FileCode2 size={28} />
            </div>

            <div className="simulator-grid">
              <label>
                Requested action
                <select
                  value={simulatedAction}
                  onChange={(event) => {
                    setSimulatedAction(
                      event.target.value,
                    );
                    setSimulationRun(false);
                  }}
                >
                  <option value="">
                    Unknown action
                  </option>

                  {rules.map((rule) => (
                    <option
                      key={rule.action}
                      value={rule.action}
                    >
                      {readableAction(
                        rule.action,
                      )}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Current risk score
                <input
                  type="number"
                  min={0}
                  max={999}
                  value={simulatedRisk}
                  onChange={(event) => {
                    setSimulatedRisk(
                      Math.max(
                        0,
                        Number(
                          event.target.value,
                        ) || 0,
                      ),
                    );
                    setSimulationRun(false);
                  }}
                />
              </label>

              <label className="simulator-toggle">
                <span>
                  Credential includes scope
                </span>

                <button
                  type="button"
                  className={
                    simulatedScoped
                      ? "enabled"
                      : ""
                  }
                  onClick={() => {
                    setSimulatedScoped(
                      (current) => !current,
                    );
                    setSimulationRun(false);
                  }}
                >
                  <span />
                  {simulatedScoped ? "YES" : "NO"}
                </button>
              </label>

              <label className="simulator-toggle">
                <span>Agent suspended</span>

                <button
                  type="button"
                  className={
                    simulatedSuspended
                      ? "danger enabled"
                      : ""
                  }
                  onClick={() => {
                    setSimulatedSuspended(
                      (current) => !current,
                    );
                    setSimulationRun(false);
                  }}
                >
                  <span />
                  {
                    simulatedSuspended
                      ? "YES"
                      : "NO"
                  }
                </button>
              </label>
            </div>

            <button
              type="button"
              className="run-simulation-button"
              onClick={() =>
                setSimulationRun(true)
              }
            >
              <GitBranch size={17} />
              Evaluate policy path
            </button>

            {result && (
              <div
                className={
                  `simulation-result ${
                    result.decision.toLowerCase()
                  }`
                }
              >
                <div className="simulation-result-icon">
                  <DecisionIcon
                    decision={result.decision}
                  />
                </div>

                <div>
                  <span>
                    Simulated decision
                  </span>
                  <h3>{result.decision}</h3>
                  <strong>{result.title}</strong>
                  <p>{result.message}</p>
                </div>

                <div className="projected-risk">
                  <span>Projected risk</span>
                  <strong>
                    {result.projectedRisk}
                  </strong>
                  <small>
                    Suspension at{" "}
                    {policy.max_risk_score}
                  </small>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
