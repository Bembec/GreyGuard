import {
  Activity,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Database,
  Fingerprint,
  RefreshCw,
  Search,
  ShieldCheck,
  TerminalSquare,
  UserCheck,
} from "lucide-react";
import {
  useMemo,
  useState,
} from "react";
import { useQuery } from "@tanstack/react-query";

import "../styles/audit-trail.css";


type AuditEvent = {
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
  details: Record<string, unknown>;
};

type AuditResponse = {
  events: AuditEvent[];
  count: number;
};

type ApiError = {
  detail?: string;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "/api";

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

async function fetchAuditEvents() {
  const response = await fetch(
    `${API_BASE_URL}/audit-events?limit=250`,
    {
      headers: adminHeaders(),
    },
  );

  return readResponse<AuditResponse>(response);
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

function eventIcon(type: string) {
  switch (type) {
    case "AUTHENTICATION":
      return <Fingerprint />;
    case "APPROVAL":
      return <UserCheck />;
    case "EXECUTION":
      return <TerminalSquare />;
    default:
      return <ShieldCheck />;
  }
}

export default function AuditTrailPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] =
    useState("ALL");
  const [outcomeFilter, setOutcomeFilter] =
    useState("ALL");
  const [expandedId, setExpandedId] =
    useState<string | null>(null);

  const auditQuery = useQuery({
    queryKey: ["administrator-audit-events"],
    queryFn: fetchAuditEvents,
    refetchInterval: 15000,
  });

  const events = auditQuery.data?.events ?? [];

  const outcomeOptions = useMemo(
    () => Array.from(
      new Set(
        events
          .map((event) => event.outcome)
          .filter(Boolean),
      ),
    ).sort(),
    [events],
  );

  const filteredEvents = useMemo(() => {
    const query = search.trim().toLowerCase();

    return events.filter((event) => {
      const matchesType =
        typeFilter === "ALL"
        || event.event_type === typeFilter;

      const matchesOutcome =
        outcomeFilter === "ALL"
        || event.outcome === outcomeFilter;

      const searchable = [
        event.event_type,
        event.agent_name,
        event.action,
        event.outcome,
        event.actor,
        event.request_id,
        event.summary,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return (
        matchesType
        && matchesOutcome
        && (!query || searchable.includes(query))
      );
    });
  }, [
    events,
    outcomeFilter,
    search,
    typeFilter,
  ]);

  const statistics = useMemo(() => ({
    total: events.length,
    policy: events.filter(
      (event) => event.event_type === "POLICY",
    ).length,
    authentication: events.filter(
      (event) =>
        event.event_type === "AUTHENTICATION",
    ).length,
    elevated: events.filter(
      (event) =>
        event.severity === "HIGH"
        || event.severity === "CRITICAL",
    ).length,
  }), [events]);

  if (auditQuery.isLoading) {
    return (
      <main className="audit-page audit-centered">
        <RefreshCw className="audit-spin" />
        <p>Reconstructing the evidence stream…</p>
      </main>
    );
  }

  if (auditQuery.isError) {
    return (
      <main className="audit-page audit-centered">
        <AlertTriangle />
        <h1>Audit evidence unavailable</h1>
        <p>
          {auditQuery.error instanceof Error
            ? auditQuery.error.message
            : "GreyGuard could not load evidence."}
        </p>
        <button
          type="button"
          onClick={() => void auditQuery.refetch()}
        >
          Try again
        </button>
      </main>
    );
  }

  return (
    <main className="audit-page">
      <div className="audit-stream-background" />
      <div className="audit-light audit-light-one" />
      <div className="audit-light audit-light-two" />

      <header className="audit-hero">
        <div>
          <span>Decision evidence</span>
          <h1>Audit Trail</h1>
          <p>
            Investigate policy decisions,
            authentication attempts, human approvals
            and controlled execution results in one
            administrator timeline.
          </p>
        </div>

        <button
          className="audit-refresh"
          type="button"
          onClick={() => void auditQuery.refetch()}
        >
          <RefreshCw />
          Refresh evidence
        </button>
      </header>

      <section className="audit-stat-grid">
        <article>
          <Database />
          <div>
            <span>Total evidence</span>
            <strong>{statistics.total}</strong>
          </div>
        </article>

        <article>
          <ShieldCheck />
          <div>
            <span>Policy events</span>
            <strong>{statistics.policy}</strong>
          </div>
        </article>

        <article>
          <Fingerprint />
          <div>
            <span>Authentication</span>
            <strong>
              {statistics.authentication}
            </strong>
          </div>
        </article>

        <article>
          <AlertTriangle />
          <div>
            <span>Elevated evidence</span>
            <strong>{statistics.elevated}</strong>
          </div>
        </article>
      </section>

      <section className="audit-console">
        <div className="audit-console-heading">
          <div>
            <span>Append-oriented record</span>
            <h2>Security evidence stream</h2>
          </div>

          <div className="audit-live">
            <i />
            Refreshes every 15 seconds
          </div>
        </div>

        <div className="audit-filters">
          <label className="audit-search">
            <Search />
            <input
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search agent, action, outcome…"
            />
          </label>

          <select
            aria-label="Filter event type"
            value={typeFilter}
            onChange={(event) =>
              setTypeFilter(event.target.value)
            }
          >
            <option value="ALL">
              All event types
            </option>
            <option value="POLICY">Policy</option>
            <option value="AUTHENTICATION">
              Authentication
            </option>
            <option value="APPROVAL">
              Approval
            </option>
            <option value="EXECUTION">
              Execution
            </option>
          </select>

          <select
            aria-label="Filter outcome"
            value={outcomeFilter}
            onChange={(event) =>
              setOutcomeFilter(event.target.value)
            }
          >
            <option value="ALL">
              All outcomes
            </option>
            {outcomeOptions.map((outcome) => (
              <option
                key={outcome}
                value={outcome}
              >
                {outcome}
              </option>
            ))}
          </select>
        </div>

        <div className="audit-results-heading">
          <span>
            {filteredEvents.length} evidence records
          </span>
          <span>Newest first</span>
        </div>

        <div className="audit-timeline">
          {filteredEvents.length === 0 ? (
            <div className="audit-empty">
              <Activity />
              <h3>No matching evidence</h3>
              <p>
                Adjust the search or filter controls.
              </p>
            </div>
          ) : (
            filteredEvents.map((event) => {
              const expanded =
                expandedId === event.event_id;

              return (
                <article
                  className="audit-event"
                  key={event.event_id}
                >
                  <div
                    className={
                      `audit-event-icon audit-${event.event_type.toLowerCase()}`
                    }
                  >
                    {eventIcon(event.event_type)}
                  </div>

                  <div className="audit-event-main">
                    <div className="audit-event-top">
                      <div>
                        <span
                          className="audit-event-type"
                        >
                          {event.event_type}
                        </span>
                        <strong>{event.summary}</strong>
                      </div>

                      <time>
                        {formatTimestamp(
                          event.timestamp,
                        )}
                      </time>
                    </div>

                    <div className="audit-event-meta">
                      <span>
                        Agent:
                        <strong>
                          {event.agent_name
                            ?? "System"}
                        </strong>
                      </span>

                      <span>
                        Action:
                        <strong>
                          {event.action
                            ?? "Not recorded"}
                        </strong>
                      </span>

                      <span
                        className={
                          `audit-outcome audit-${event.severity.toLowerCase()}`
                        }
                      >
                        {event.outcome}
                      </span>
                    </div>

                    {expanded && (
                      <div className="audit-evidence">
                        <div>
                          <span>Event ID</span>
                          <code>{event.event_id}</code>
                        </div>
                        <div>
                          <span>Actor</span>
                          <code>
                            {event.actor ?? "System"}
                          </code>
                        </div>
                        {event.request_id && (
                          <div>
                            <span>Request ID</span>
                            <code>
                              {event.request_id}
                            </code>
                          </div>
                        )}
                        <div className="audit-json">
                          <span>Recorded evidence</span>
                          <pre>
                            {JSON.stringify(
                              event.details,
                              null,
                              2,
                            )}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>

                  <button
                    className="audit-expand"
                    type="button"
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
      </section>
    </main>
  );
}
