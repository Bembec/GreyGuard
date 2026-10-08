import {
  AlertTriangle,
  Check,
  Copy,
  KeyRound,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  UserRoundCheck,
  UserRoundX,
  X,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { usePermission } from "../hooks/usePermission";
import "../styles/agents.css";


type CredentialStatus =
  | "ACTIVE"
  | "REVOKED"
  | "MISSING"
  | string;

type AgentIdentity = {
  agent_name?: string;
  scopes?: string[];
  credential_status?: CredentialStatus;
  created_at?: string | null;
  rotated_at?: string | null;
  revoked_at?: string | null;
};

type Agent = {
  agent_name: string;
  agent_status: string;
  risk_score: number;
  risk_level: string;
  blocked_attempts: number;
  identity?: AgentIdentity | null;
};

type CredentialResponse = {
  agent_name?: string;
  credential?: string;
  credential_notice?: string;
  identity?: AgentIdentity;
};

type ScopeResponse = {
  updated?: boolean;
  identity?: AgentIdentity;
};

type ApiError = {
  detail?: string;
};

type AgentConfirmation = "rotate" | "revoke" | "reset" | null;

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "/api";

const availableScopes = [
  "audit_summary",
  "list_files",
  "read_file",
  "search_logs",
  "view_audit",
  "write_note",
];

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

async function updateAgentScopes(
  agentName: string,
  scopes: string[],
): Promise<ScopeResponse> {
  const response = await fetch(
    `${API_BASE_URL}/agents/${encodeURIComponent(
      agentName,
    )}/scopes`,
    {
      method: "PUT",
      headers: adminHeaders(),
      body: JSON.stringify({ scopes }),
    },
  );

  return readResponse<ScopeResponse>(response);
}

async function rotateCredential(
  agentName: string,
): Promise<CredentialResponse> {
  const response = await fetch(
    `${API_BASE_URL}/agents/${encodeURIComponent(
      agentName,
    )}/credential/rotate`,
    {
      method: "POST",
      headers: adminHeaders(),
    },
  );

  return readResponse<CredentialResponse>(response);
}

async function revokeCredential(
  agentName: string,
): Promise<CredentialResponse> {
  const response = await fetch(
    `${API_BASE_URL}/agents/${encodeURIComponent(
      agentName,
    )}/credential/revoke`,
    {
      method: "POST",
      headers: adminHeaders(),
    },
  );

  return readResponse<CredentialResponse>(response);
}

async function resetAgent(
  agentName: string,
): Promise<unknown> {
  const response = await fetch(
    `${API_BASE_URL}/agents/${encodeURIComponent(
      agentName,
    )}/reset`,
    {
      method: "POST",
      headers: adminHeaders(),
    },
  );

  return readResponse<unknown>(response);
}

function classNameForRisk(riskLevel: string) {
  return `risk-${riskLevel.toLowerCase()}`;
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

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  // Every /agents mutation route requires identity:manage server-side (admin_auth.py's
  // required_permission), which only PLATFORM_ADMIN holds - gate the controls to match,
  // rather than letting a SECURITY_ANALYST or AUDITOR click them and get a raw 403.
  const canManageIdentity = usePermission({ permission: "identity:manage" });

  const [searchText, setSearchText] =
    useState("");
  const [statusFilter, setStatusFilter] =
    useState("ALL");
  const [selectedName, setSelectedName] =
    useState<string | null>(null);
  const [selectedScopes, setSelectedScopes] =
    useState<string[]>([]);
  const [revealedCredential, setRevealedCredential] =
    useState<string | null>(null);
  const [credentialCopied, setCredentialCopied] =
    useState(false);
  const [notice, setNotice] =
    useState<string | null>(null);
  const [confirmation, setConfirmation] =
    useState<AgentConfirmation>(null);

  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    refetchInterval: 30_000,
  });

  const agents = agentsQuery.data ?? [];

  const selectedAgent = useMemo(
    () => agents.find(
      (agent) =>
        agent.agent_name === selectedName,
    ) ?? null,
    [agents, selectedName],
  );

  useEffect(() => {
    setSelectedScopes(
      selectedAgent?.identity?.scopes ?? [],
    );
  }, [selectedAgent]);

  const filteredAgents = useMemo(() => {
    const normalizedSearch =
      searchText.trim().toLowerCase();

    return agents.filter((agent) => {
      const matchesSearch =
        !normalizedSearch
        || agent.agent_name
          .toLowerCase()
          .includes(normalizedSearch);

      const matchesStatus =
        statusFilter === "ALL"
        || agent.agent_status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [agents, searchText, statusFilter]);

  const mutationOptions = {
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["agents"],
      });
    },
    onError: (error: Error) => {
      setNotice(error.message);
    },
  };

  const scopesMutation = useMutation({
    mutationFn: ({
      agentName,
      scopes,
    }: {
      agentName: string;
      scopes: string[];
    }) => updateAgentScopes(agentName, scopes),
    ...mutationOptions,
    onSuccess: async () => {
      setNotice("Agent scopes updated successfully.");
      await queryClient.invalidateQueries({
        queryKey: ["agents"],
      });
    },
  });

  const rotateMutation = useMutation({
    mutationFn: rotateCredential,
    ...mutationOptions,
    onSuccess: async (result) => {
      setRevealedCredential(
        result.credential ?? null,
      );
      setCredentialCopied(false);
      setNotice(
        result.credential_notice
        ?? "Credential rotated successfully.",
      );

      await queryClient.invalidateQueries({
        queryKey: ["agents"],
      });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: revokeCredential,
    ...mutationOptions,
    onSuccess: async () => {
      setNotice("Agent credential revoked.");
      await queryClient.invalidateQueries({
        queryKey: ["agents"],
      });
    },
  });

  const resetMutation = useMutation({
    mutationFn: resetAgent,
    ...mutationOptions,
    onSuccess: async () => {
      setNotice(
        "Agent security state reset successfully.",
      );
      await queryClient.invalidateQueries({
        queryKey: ["agents"],
      });
    },
  });

  const activeAgents = agents.filter(
    (agent) => agent.agent_status === "ACTIVE",
  ).length;

  const suspendedAgents = agents.filter(
    (agent) =>
      agent.agent_status === "SUSPENDED",
  ).length;

  const protectedIdentities = agents.filter(
    (agent) =>
      agent.identity?.credential_status === "ACTIVE",
  ).length;

  const highRiskAgents = agents.filter(
    (agent) =>
      agent.risk_level === "HIGH"
      || agent.risk_level === "CRITICAL",
  ).length;

  function toggleScope(scope: string) {
    setSelectedScopes((currentScopes) => {
      if (currentScopes.includes(scope)) {
        return currentScopes.filter(
          (currentScope) =>
            currentScope !== scope,
        );
      }

      return [
        ...currentScopes,
        scope,
      ].sort();
    });
  }

  async function copyCredential() {
    if (!revealedCredential) {
      return;
    }

    await navigator.clipboard.writeText(
      revealedCredential,
    );

    setCredentialCopied(true);
  }

  return (
    <main className="agents-page">
      <div
        className="agents-watermark"
        aria-hidden="true"
      />

      <section className="agents-heading">
        <div>
          <div className="section-kicker">
            Identity control plane
          </div>

          <h1>Govern every agent independently.</h1>

          <p>
            Agent identity is not agent permission.
            Inspect security posture, restrict scopes,
            rotate credentials, and contain risky agents
            from one command surface.
          </p>
        </div>

        <button
          type="button"
          className="agents-refresh-button"
          onClick={() => agentsQuery.refetch()}
          disabled={agentsQuery.isFetching}
        >
          <RefreshCw
            size={17}
            className={
              agentsQuery.isFetching
                ? "spin"
                : undefined
            }
          />
          Refresh agents
        </button>
      </section>

      <section className="agent-stat-grid">
        <article className="agent-stat-card cyan">
          <ShieldCheck size={22} />
          <span>Registered agents</span>
          <strong>{agents.length}</strong>
          <small>
            Independent identities in GreyGuard
          </small>
        </article>

        <article className="agent-stat-card green">
          <UserRoundCheck size={22} />
          <span>Active</span>
          <strong>{activeAgents}</strong>
          <small>Available under current policy</small>
        </article>

        <article className="agent-stat-card violet">
          <KeyRound size={22} />
          <span>Protected identities</span>
          <strong>{protectedIdentities}</strong>
          <small>Credentials currently active</small>
        </article>

        <article className="agent-stat-card red">
          <ShieldAlert size={22} />
          <span>High-risk or suspended</span>
          <strong>
            {highRiskAgents + suspendedAgents}
          </strong>
          <small>Requires security attention</small>
        </article>
      </section>

      {notice && (
        <div className="agents-notice">
          <span>{notice}</span>

          <button
            type="button"
            aria-label="Dismiss notification"
            onClick={() => setNotice(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}

      <section className="agents-workspace">
        <div className="agents-list-panel">
          <div className="agents-toolbar">
            <label className="agents-search">
              <Search size={17} />
              <input
                type="search"
                value={searchText}
                onChange={(event) =>
                  setSearchText(event.target.value)
                }
                placeholder="Search agent identity..."
              />
            </label>

            <label className="agents-filter">
              <SlidersHorizontal size={16} />
              <select
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value)
                }
              >
                <option value="ALL">
                  All statuses
                </option>
                <option value="ACTIVE">
                  Active
                </option>
                <option value="SUSPENDED">
                  Suspended
                </option>
              </select>
            </label>
          </div>

          {agentsQuery.isLoading && (
            <div className="agents-state-panel">
              <RefreshCw
                className="spin"
                size={25}
              />
              <strong>
                Loading governed identities
              </strong>
              <span>
                Reading the GreyGuard control plane.
              </span>
            </div>
          )}

          {agentsQuery.isError && (
            <div className="agents-state-panel error">
              <AlertTriangle size={25} />
              <strong>
                Agents could not be loaded
              </strong>
              <span>
                {(
                  agentsQuery.error as Error
                ).message}
              </span>

              <button
                type="button"
                onClick={() =>
                  agentsQuery.refetch()
                }
              >
                Try again
              </button>
            </div>
          )}

          {!agentsQuery.isLoading
            && !agentsQuery.isError
            && (
              <div className="agent-table-wrapper">
                <table className="agent-table">
                  <thead>
                    <tr>
                      <th>Agent identity</th>
                      <th>Status</th>
                      <th>Risk</th>
                      <th>Credential</th>
                      <th>Scopes</th>
                      <th aria-label="Open details" />
                    </tr>
                  </thead>

                  <tbody>
                    {filteredAgents.map((agent) => (
                      <tr
                        key={agent.agent_name}
                        className={
                          selectedName
                            === agent.agent_name
                            ? "selected"
                            : undefined
                        }
                        onClick={() =>
                          setSelectedName(
                            agent.agent_name,
                          )
                        }
                      >
                        <td>
                          <div className="agent-name-cell">
                            <div className="agent-avatar">
                              {agent.agent_name
                                .charAt(0)
                                .toUpperCase()}
                            </div>

                            <div>
                              <strong>
                                {agent.agent_name}
                              </strong>
                              <span>
                                {agent.blocked_attempts}
                                {" "}
                                blocked attempts
                              </span>
                            </div>
                          </div>
                        </td>

                        <td>
                          <span
                            className={
                              `agent-status ${
                                agent.agent_status
                                  .toLowerCase()
                              }`
                            }
                          >
                            {agent.agent_status}
                          </span>
                        </td>

                        <td>
                          <div className="agent-risk-cell">
                            <span
                              className={
                                `risk-label ${
                                  classNameForRisk(
                                    agent.risk_level,
                                  )
                                }`
                              }
                            >
                              {agent.risk_level}
                            </span>

                            <div className="risk-track">
                              <span
                                style={{
                                  width: `${
                                    Math.min(
                                      agent.risk_score,
                                      100,
                                    )
                                  }%`,
                                }}
                              />
                            </div>

                            <small>
                              {agent.risk_score}
                            </small>
                          </div>
                        </td>

                        <td>
                          <span
                            className={
                              `credential-status ${
                                (
                                  agent.identity
                                    ?.credential_status
                                  ?? "MISSING"
                                ).toLowerCase()
                              }`
                            }
                          >
                            {agent.identity
                              ?.credential_status
                              ?? "MISSING"}
                          </span>
                        </td>

                        <td>
                          {
                            agent.identity
                              ?.scopes?.length ?? 0
                          }
                        </td>

                        <td>
                          <button
                            type="button"
                            className="inspect-button"
                            onClick={(event) => {
                              event.stopPropagation();
                              navigate(`/agents/${encodeURIComponent(agent.agent_name)}`);
                            }}
                          >
                            Investigate
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {filteredAgents.length === 0 && (
                  <div className="agents-empty">
                    <Search size={24} />
                    <strong>No matching agents</strong>
                    <span>
                      Change your search or status filter.
                    </span>
                  </div>
                )}
              </div>
            )}
        </div>

        <aside
          className={
            `agent-detail-panel ${
              selectedAgent ? "open" : ""
            }`
          }
        >
          {!selectedAgent ? (
            <div className="agent-detail-empty">
              <div className="detail-orbit">
                <ShieldCheck size={36} />
              </div>

              <strong>Select an agent</strong>

              <p>
                Choose an identity to inspect its
                permissions, credentials, risk, and
                containment controls.
              </p>
            </div>
          ) : (
            <>
              <div className="detail-header">
                <div>
                  <span>Agent identity</span>
                  <h2>
                    {selectedAgent.agent_name}
                  </h2>
                </div>

                <button
                  type="button"
                  aria-label="Close agent details"
                  onClick={() =>
                    setSelectedName(null)
                  }
                >
                  <X size={18} />
                </button>
              </div>

              <div className="detail-posture">
                <div>
                  <span>Security status</span>
                  <strong>
                    {selectedAgent.agent_status}
                  </strong>
                </div>

                <div>
                  <span>Current risk</span>
                  <strong
                    className={
                      classNameForRisk(
                        selectedAgent.risk_level,
                      )
                    }
                  >
                    {selectedAgent.risk_score}
                    {" · "}
                    {selectedAgent.risk_level}
                  </strong>
                </div>

                <div>
                  <span>Blocked attempts</span>
                  <strong>
                    {
                      selectedAgent.blocked_attempts
                    }
                  </strong>
                </div>

                <div>
                  <span>Credential</span>
                  <strong>
                    {selectedAgent.identity
                      ?.credential_status
                      ?? "MISSING"}
                  </strong>
                </div>
              </div>

              <div className="detail-section">
                <div className="detail-section-heading">
                  <div>
                    <h3>Scope boundaries</h3>
                    <p>
                      Identity confirms who the agent is.
                      Scopes control what it may request.
                    </p>
                  </div>
                </div>

                {selectedAgent.identity ? (
                  <>
                    <div className="scope-selector">
                      {availableScopes.map((scope) => {
                        const selected =
                          selectedScopes.includes(scope);

                        return (
                          <button
                            type="button"
                            key={scope}
                            className={
                              selected
                                ? "selected"
                                : ""
                            }
                            disabled={!canManageIdentity}
                            onClick={() =>
                              toggleScope(scope)
                            }
                          >
                            {selected && (
                              <Check size={14} />
                            )}
                            {scope}
                          </button>
                        );
                      })}
                    </div>

                    {canManageIdentity ? (
                      <button
                        type="button"
                        className="detail-primary-button"
                        disabled={
                          scopesMutation.isPending
                        }
                        onClick={() =>
                          scopesMutation.mutate({
                            agentName:
                              selectedAgent.agent_name,
                            scopes: selectedScopes,
                          })
                        }
                      >
                        {scopesMutation.isPending
                          ? "Saving boundaries..."
                          : "Save scope boundaries"}
                      </button>
                    ) : (
                      <p className="gg-readonly-note">
                        Your role has read-only access to scope boundaries.
                        Platform Administrator access is required to change them.
                      </p>
                    )}
                  </>
                ) : (
                  <div className="identity-warning">
                    <AlertTriangle size={18} />
                    This legacy agent has no registered
                    V9 identity or scoped credential.
                  </div>
                )}
              </div>

              {selectedAgent.identity && (
                <div className="detail-section">
                  <h3>Credential lifecycle</h3>

                  <div className="identity-dates">
                    <span>
                      Created
                      <strong>
                        {formatDate(
                          selectedAgent.identity
                            .created_at,
                        )}
                      </strong>
                    </span>

                    <span>
                      Last rotated
                      <strong>
                        {formatDate(
                          selectedAgent.identity
                            .rotated_at,
                        )}
                      </strong>
                    </span>
                  </div>

                  {canManageIdentity ? (
                    <div className="detail-action-row">
                      <button
                        type="button"
                        className="detail-secondary-button"
                        disabled={
                          rotateMutation.isPending
                        }
                        onClick={() => setConfirmation("rotate")}
                      >
                        <KeyRound size={16} />
                        Rotate credential
                      </button>

                      <button
                        type="button"
                        className="detail-danger-button"
                        disabled={
                          revokeMutation.isPending
                          || selectedAgent.identity
                            .credential_status
                            === "REVOKED"
                        }
                        onClick={() => setConfirmation("revoke")}
                      >
                        <UserRoundX size={16} />
                        Revoke
                      </button>
                    </div>
                  ) : (
                    <p className="gg-readonly-note">
                      Platform Administrator access is required to rotate or revoke credentials.
                    </p>
                  )}
                </div>
              )}

              {canManageIdentity && (
              <div className="detail-section containment">
                <h3>Containment recovery</h3>

                <p>
                  Administrative reset clears the
                  agent’s accumulated risk, blocked
                  attempts, and suspension state. The
                  action is recorded in the audit trail.
                </p>

                <button
                  type="button"
                  className="detail-reset-button"
                  disabled={resetMutation.isPending}
                  onClick={() => setConfirmation("reset")}
                >
                  <RotateCcw size={16} />
                  Reset security state
                </button>
              </div>
              )}
            </>
          )}
        </aside>
      </section>

      {revealedCredential && (
        <div
          className="credential-modal-backdrop"
          role="presentation"
        >
          <section
            className="credential-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="credential-title"
          >
            <div className="credential-modal-icon">
              <KeyRound size={26} />
            </div>

            <span>One-time credential</span>

            <h2 id="credential-title">
              Save this credential now
            </h2>

            <p>
              GreyGuard stores only its secure hash.
              This credential will not be displayed
              again after you close this window.
            </p>

            <div className="credential-value">
              <code>{revealedCredential}</code>

              <button
                type="button"
                onClick={copyCredential}
              >
                {credentialCopied ? (
                  <Check size={17} />
                ) : (
                  <Copy size={17} />
                )}
              </button>
            </div>

            <button
              type="button"
              className="credential-close-button"
              onClick={() => {
                setRevealedCredential(null);
                setCredentialCopied(false);
              }}
            >
              I have saved the credential
            </button>
          </section>
        </div>
      )}

      <ConfirmDialog
        open={confirmation !== null}
        title={confirmation === "rotate" ? "Rotate agent credential?" : confirmation === "revoke" ? "Revoke agent credential?" : "Reset agent security state?"}
        description={confirmation === "rotate" ? "The existing credential will stop working immediately." : confirmation === "revoke" ? "The agent will no longer be able to authenticate." : "Accumulated risk, blocked attempts, and suspension state will be cleared. This action is audited."}
        confirmLabel={confirmation === "rotate" ? "Rotate credential" : confirmation === "revoke" ? "Revoke credential" : "Reset security state"}
        tone={confirmation === "rotate" ? "warning" : "danger"}
        busy={rotateMutation.isPending || revokeMutation.isPending || resetMutation.isPending}
        onCancel={() => setConfirmation(null)}
        onConfirm={() => {
          if (!selectedAgent || !confirmation) return;
          const agentName = selectedAgent.agent_name;
          const complete = { onSettled: () => setConfirmation(null) };
          if (confirmation === "rotate") rotateMutation.mutate(agentName, complete);
          else if (confirmation === "revoke") revokeMutation.mutate(agentName, complete);
          else resetMutation.mutate(agentName, complete);
        }}
      />
    </main>
  );
}
