import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Fingerprint,
  KeyRound,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  UserX,
} from "lucide-react";
import {
  useMemo,
  useState,
} from "react";
import { useQuery } from "@tanstack/react-query";

import { ErrorState, LoadingState } from "../components/AsyncState";
import "../styles/authentication.css";


type AuthenticationEvent = {
  event_id: string;
  event_type: string;
  timestamp: string;
  agent_name: string | null;
  action: string | null;
  outcome: string;
  severity: string;
  request_id: string | null;
  actor: string | null;
  summary: string;
  details: {
    claimed_agent_name?: string | null;
    authenticated_agent_name?: string | null;
    reason?: string | null;
    [key: string]: unknown;
  };
};

type AuditResponse = {
  events: AuthenticationEvent[];
  count: number;
};

type AgentIdentity = {
  agent_name?: string;
  scopes?: string[];
  credential_status?: string;
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

type ApiError = {
  detail?: string;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "/api";

const successfulOutcomes = new Set([
  "AUTHENTICATED",
  "AUTHORIZED",
  "SUCCESS",
]);

function adminHeaders() {
  const pin = sessionStorage.getItem(
    "greyguard_admin_pin",
  );

  if (!pin) {
    throw new Error(
      "Administrator session is missing. Sign in again.",
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

async function fetchAuthenticationEvents() {
  const response = await fetch(
    `${API_BASE_URL}/audit-events?event_type=AUTHENTICATION&limit=500`,
    {
      headers: adminHeaders(),
    },
  );

  return readResponse<AuditResponse>(response);
}

async function fetchAgents() {
  const response = await fetch(
    `${API_BASE_URL}/agents`,
    {
      headers: adminHeaders(),
    },
  );

  return readResponse<Agent[]>(response);
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
      timeStyle: "medium",
    },
  ).format(date);
}

function isSuccessful(outcome: string) {
  return successfulOutcomes.has(
    outcome.toUpperCase(),
  );
}

function isScopeDenial(event: AuthenticationEvent) {
  const searchable = [
    event.outcome,
    event.summary,
    event.details.reason,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return (
    searchable.includes("scope")
    || searchable.includes("resource_denied")
  );
}

export default function AuthenticationPage() {
  const [search, setSearch] = useState("");
  const [outcomeFilter, setOutcomeFilter] =
    useState("ALL");
  const [agentFilter, setAgentFilter] =
    useState("ALL");
  const [expandedId, setExpandedId] =
    useState<string | null>(null);

  const authenticationQuery = useQuery({
    queryKey: ["authentication-intelligence"],
    queryFn: fetchAuthenticationEvents,
    refetchInterval: 15000,
  });

  const agentsQuery = useQuery({
    queryKey: ["agents", "authentication"],
    queryFn: fetchAgents,
    refetchInterval: 15000,
  });

  const events =
    authenticationQuery.data?.events ?? [];
  const agents = agentsQuery.data ?? [];

  const statistics = useMemo(() => {
    const successful = events.filter(
      (event) => isSuccessful(event.outcome),
    ).length;

    const denied = events.length - successful;

    const scopeDenials = events.filter(
      isScopeDenial,
    ).length;

    const activeCredentials = agents.filter(
      (agent) =>
        agent.identity?.credential_status
        === "ACTIVE",
    ).length;

    return {
      successful,
      denied,
      scopeDenials,
      activeCredentials,
    };
  }, [agents, events]);

  const agentOptions = useMemo(
    () => Array.from(
      new Set(
        events
          .map((event) => event.agent_name)
          .filter(
            (name): name is string =>
              Boolean(name),
          ),
      ),
    ).sort(),
    [events],
  );

  const filteredEvents = useMemo(() => {
    const query = search.trim().toLowerCase();

    return events.filter((event) => {
      const successful =
        isSuccessful(event.outcome);

      const matchesOutcome =
        outcomeFilter === "ALL"
        || (
          outcomeFilter === "SUCCESS"
          && successful
        )
        || (
          outcomeFilter === "DENIED"
          && !successful
        )
        || (
          outcomeFilter === "SCOPE_DENIED"
          && isScopeDenial(event)
        );

      const matchesAgent =
        agentFilter === "ALL"
        || event.agent_name === agentFilter;

      const searchable = [
        event.agent_name,
        event.action,
        event.outcome,
        event.summary,
        event.actor,
        event.details.claimed_agent_name,
        event.details.authenticated_agent_name,
        event.details.reason,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return (
        matchesOutcome
        && matchesAgent
        && (!query || searchable.includes(query))
      );
    });
  }, [
    agentFilter,
    events,
    outcomeFilter,
    search,
  ]);

  if (
    authenticationQuery.isLoading
    || agentsQuery.isLoading
  ) {
    return (
      <main className="authentication-page auth-centered">
        <LoadingState label="Verifying identity evidence" rows={5} />
      </main>
    );
  }

  if (
    authenticationQuery.isError
    || agentsQuery.isError
  ) {
    const error =
      authenticationQuery.error
      ?? agentsQuery.error;

    return (
      <main className="authentication-page auth-centered">
        <ErrorState message={error instanceof Error ? error.message : "GreyGuard could not load identity evidence."} onRetry={() => { void authenticationQuery.refetch(); void agentsQuery.refetch(); }} />
      </main>
    );
  }

  return (
    <main className="authentication-page">
      <div className="auth-identity-grid" />
      <div className="auth-scan-line" />
      <div className="auth-glow auth-glow-one" />
      <div className="auth-glow auth-glow-two" />

      <header className="auth-hero">
        <div>
          <span>Identity assurance</span>
          <h1>Authentication Intelligence</h1>
          <p>
            Investigate identity claims, credential
            verification, scope boundaries and denied
            access across GreyGuard’s independent agents.
          </p>
        </div>

        <div className="auth-live">
          <i />
          Live identity telemetry
        </div>
      </header>

      <section className="auth-stat-grid">
        <article>
          <div className="auth-stat-icon success">
            <UserCheck />
          </div>
          <div>
            <span>Successful</span>
            <strong>{statistics.successful}</strong>
            <small>Verified requests</small>
          </div>
        </article>

        <article>
          <div className="auth-stat-icon danger">
            <UserX />
          </div>
          <div>
            <span>Denied</span>
            <strong>{statistics.denied}</strong>
            <small>Rejected identity attempts</small>
          </div>
        </article>

        <article>
          <div className="auth-stat-icon warning">
            <ShieldAlert />
          </div>
          <div>
            <span>Scope denials</span>
            <strong>{statistics.scopeDenials}</strong>
            <small>Identity lacked permission</small>
          </div>
        </article>

        <article>
          <div className="auth-stat-icon active">
            <KeyRound />
          </div>
          <div>
            <span>Active credentials</span>
            <strong>
              {statistics.activeCredentials}
            </strong>
            <small>Usable agent identities</small>
          </div>
        </article>
      </section>

      <section className="auth-layout">
        <article className="auth-panel auth-events-panel">
          <div className="auth-panel-heading">
            <div>
              <span>Verification stream</span>
              <h2>Authentication events</h2>
            </div>

            <button
              type="button"
              className="auth-refresh"
              onClick={() =>
                void authenticationQuery.refetch()
              }
            >
              <RefreshCw />
              Refresh
            </button>
          </div>

          <div className="auth-filters">
            <label className="auth-search">
              <Search />
              <input
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Search identity, action or reason…"
              />
            </label>

            <select
              value={agentFilter}
              aria-label="Filter agent"
              onChange={(event) =>
                setAgentFilter(event.target.value)
              }
            >
              <option value="ALL">
                All identities
              </option>
              {agentOptions.map((agent) => (
                <option
                  value={agent}
                  key={agent}
                >
                  {agent}
                </option>
              ))}
            </select>

            <select
              value={outcomeFilter}
              aria-label="Filter outcome"
              onChange={(event) =>
                setOutcomeFilter(event.target.value)
              }
            >
              <option value="ALL">
                All outcomes
              </option>
              <option value="SUCCESS">
                Successful
              </option>
              <option value="DENIED">
                Denied
              </option>
              <option value="SCOPE_DENIED">
                Scope denied
              </option>
            </select>
          </div>

          <div className="auth-result-count">
            <span>
              {filteredEvents.length} matching events
            </span>
            <span>Newest first</span>
          </div>

          <div className="auth-event-list">
            {filteredEvents.length === 0 ? (
              <div className="auth-empty">
                <Fingerprint />
                <h3>No matching identity evidence</h3>
                <p>
                  Adjust the current filters or search.
                </p>
              </div>
            ) : (
              filteredEvents.map((event) => {
                const successful =
                  isSuccessful(event.outcome);
                const expanded =
                  expandedId === event.event_id;

                return (
                  <article
                    className="auth-event"
                    key={event.event_id}
                  >
                    <div
                      className={
                        successful
                          ? "auth-event-icon success"
                          : "auth-event-icon danger"
                      }
                    >
                      {successful
                        ? <CheckCircle2 />
                        : <ShieldAlert />}
                    </div>

                    <div className="auth-event-content">
                      <div className="auth-event-top">
                        <div>
                          <span>
                            {successful
                              ? "VERIFIED"
                              : "DENIED"}
                          </span>
                          <strong>
                            {event.agent_name
                              ?? "Unknown identity"}
                          </strong>
                        </div>

                        <time>
                          {formatTimestamp(
                            event.timestamp,
                          )}
                        </time>
                      </div>

                      <p>{event.summary}</p>

                      <div className="auth-event-meta">
                        <span>
                          Action:
                          <strong>
                            {event.action
                              ?? "Not recorded"}
                          </strong>
                        </span>

                        <span
                          className={
                            successful
                              ? "auth-outcome success"
                              : "auth-outcome danger"
                          }
                        >
                          {event.outcome}
                        </span>
                      </div>

                      {expanded && (
                        <div className="auth-evidence">
                          <div>
                            <span>Claimed identity</span>
                            <code>
                              {
                                event.details
                                  .claimed_agent_name
                                ?? "Not provided"
                              }
                            </code>
                          </div>

                          <div>
                            <span>
                              Authenticated identity
                            </span>
                            <code>
                              {
                                event.details
                                  .authenticated_agent_name
                                ?? "Not authenticated"
                              }
                            </code>
                          </div>

                          <div>
                            <span>Reason</span>
                            <code>
                              {
                                event.details.reason
                                ?? event.summary
                              }
                            </code>
                          </div>

                          <div>
                            <span>Evidence ID</span>
                            <code>{event.event_id}</code>
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      className="auth-expand"
                      aria-label={
                        expanded
                          ? "Collapse evidence"
                          : "Expand evidence"
                      }
                      onClick={() =>
                        setExpandedId(
                          expanded
                            ? null
                            : event.event_id,
                        )
                      }
                    >
                      {expanded
                        ? <ChevronUp />
                        : <ChevronDown />}
                    </button>
                  </article>
                );
              })
            )}
          </div>
        </article>

        <aside className="auth-side-column">
          <article className="auth-panel">
            <div className="auth-panel-heading">
              <div>
                <span>Credential posture</span>
                <h2>Agent identities</h2>
              </div>
              <Fingerprint />
            </div>

            <div className="auth-identity-list">
              {agents.map((agent) => {
                const credentialStatus =
                  agent.identity?.credential_status
                  ?? "MISSING";

                return (
                  <div
                    className="auth-identity-row"
                    key={agent.agent_name}
                  >
                    <div className="auth-avatar">
                      {agent.agent_name
                        .slice(0, 2)
                        .toUpperCase()}
                    </div>

                    <div>
                      <strong>
                        {agent.agent_name}
                      </strong>
                      <small>
                        {
                          agent.identity?.scopes
                            ?.length ?? 0
                        } assigned scopes
                      </small>
                    </div>

                    <span
                      className={
                        credentialStatus === "ACTIVE"
                          ? "credential-active"
                          : "credential-inactive"
                      }
                    >
                      {credentialStatus}
                    </span>
                  </div>
                );
              })}
            </div>
          </article>

          <article className="auth-panel auth-principle">
            <ShieldCheck />
            <span>Core security principle</span>
            <h2>
              Agent identity ≠ agent permission
            </h2>
            <p>
              A valid credential proves which agent is
              making a request. Its assigned scopes
              determine what that identity may do.
            </p>
          </article>

          <article className="auth-panel auth-boundary">
            <KeyRound />
            <div>
              <span>Boundary model</span>
              <strong>
                Identity → Scope → Policy → Action
              </strong>
            </div>
          </article>
        </aside>
      </section>
    </main>
  );
}
