import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CirclePause,
  CirclePlay,
  Clock3,
  Eraser,
  Filter,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Signal,
  WifiOff,
  XCircle,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import "../styles/live-operations.css";


type ConnectionStatus =
  | "CONNECTING"
  | "CONNECTED"
  | "RECONNECTING"
  | "PAUSED"
  | "DISCONNECTED"
  | "ERROR";

type EventSeverity =
  | "INFO"
  | "LOW"
  | "MEDIUM"
  | "HIGH"
  | "CRITICAL"
  | string;

type SecurityEvent = {
  event_id: string;
  event_type: string;
  timestamp: string;
  agent_name: string | null;
  action: string | null;
  outcome: string;
  severity: EventSeverity;
  request_id: string | null;
  actor: string | null;
  summary: string;
  details: Record<string, unknown>;
};

type StreamEnvelope = {
  status?: string;
  application?: string;
  stream?: string;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "/api";

const eventTypes = [
  "ALL",
  "POLICY",
  "AUTHENTICATION",
  "APPROVAL",
  "EXECUTION",
];

const severityOrder: Record<string, number> = {
  INFO: 0,
  LOW: 1,
  MEDIUM: 2,
  HIGH: 3,
  CRITICAL: 4,
};

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

export function severityClass(severity: string) {
  return `live-severity live-severity--${severity.toLowerCase()}`;
}

function eventIcon(eventType: string) {
  switch (eventType) {
    case "AUTHENTICATION":
      return ShieldCheck;
    case "APPROVAL":
      return CheckCircle2;
    case "EXECUTION":
      return Activity;
    case "POLICY":
      return ShieldAlert;
    default:
      return Radio;
  }
}

export function connectionLabel(
  status: ConnectionStatus,
) {
  switch (status) {
    case "CONNECTED":
      return "Live connection active";
    case "CONNECTING":
      return "Opening secure stream";
    case "RECONNECTING":
      return "Reconnecting automatically";
    case "PAUSED":
      return "Monitoring paused";
    case "ERROR":
      return "Connection needs attention";
    default:
      return "Stream disconnected";
  }
}

export function parseSseMessage(
  block: string,
): {
  id: string | null;
  event: string;
  data: string;
} | null {
  const lines = block
    .split(/\r?\n/)
    .filter((line) => !line.startsWith(":"));

  let id: string | null = null;
  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("id:")) {
      id = line.slice(3).trim();
    } else if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return {
    id,
    event,
    data: dataLines.join("\n"),
  };
}

export default function LiveOperationsPage() {
  const [events, setEvents] = useState<
    SecurityEvent[]
  >([]);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("CONNECTING");
  const [connectionError, setConnectionError] =
    useState("");
  const [paused, setPaused] = useState(false);
  const [eventType, setEventType] =
    useState("ALL");
  const [minimumSeverity, setMinimumSeverity] =
    useState("INFO");
  const [agentFilter, setAgentFilter] =
    useState("");
  const [searchText, setSearchText] =
    useState("");
  const [expandedEvent, setExpandedEvent] =
    useState<string | null>(null);
  const [connectionAttempt, setConnectionAttempt] =
    useState(0);
  const [lastEventAt, setLastEventAt] =
    useState<string | null>(null);

  const seenEventIds = useRef(new Set<string>());

  useEffect(() => {
    if (paused) {
      setConnectionStatus("PAUSED");
      return;
    }

    const controller = new AbortController();
    let reconnectTimer:
      | ReturnType<typeof setTimeout>
      | undefined;
    let intentionallyClosed = false;

    async function connect() {
      const adminPin = sessionStorage.getItem(
        "greyguard_admin_pin",
      );

      if (!adminPin) {
        setConnectionStatus("ERROR");
        setConnectionError(
          "Administrator session is missing. Sign in again.",
        );
        return;
      }

      setConnectionStatus((current) =>
        current === "DISCONNECTED"
        || current === "ERROR"
          ? "RECONNECTING"
          : "CONNECTING",
      );
      setConnectionError("");

      const parameters = new URLSearchParams({
        include_history: "true",
        limit: "100",
        poll_interval: "1",
      });

      if (eventType !== "ALL") {
        parameters.set("event_type", eventType);
      }

      if (agentFilter.trim()) {
        parameters.set(
          "agent_name",
          agentFilter.trim(),
        );
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/live-events?${parameters.toString()}`,
          {
            headers: {
              "x-admin-pin": adminPin,
              Accept: "text/event-stream",
            },
            cache: "no-store",
            signal: controller.signal,
          },
        );

        if (!response.ok) {
          let detail =
            `Live stream failed with status ${response.status}.`;

          try {
            const body = (
              await response.json()
            ) as { detail?: string };

            detail = body.detail ?? detail;
          } catch {
            // Use the HTTP status message.
          }

          throw new Error(detail);
        }

        if (!response.body) {
          throw new Error(
            "Streaming response body is unavailable.",
          );
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } =
            await reader.read();

          if (done) {
            break;
          }

          buffer += decoder.decode(
            value,
            { stream: true },
          );

          const messageBlocks =
            buffer.split(/\r?\n\r?\n/);

          buffer = messageBlocks.pop() ?? "";

          for (const block of messageBlocks) {
            const message = parseSseMessage(block);

            if (!message) {
              continue;
            }

            if (message.event === "stream-ready") {
              const envelope = JSON.parse(
                message.data,
              ) as StreamEnvelope;

              if (envelope.status === "connected") {
                setConnectionStatus("CONNECTED");
              }

              continue;
            }

            if (message.event === "heartbeat") {
              setConnectionStatus("CONNECTED");
              continue;
            }

            if (
              message.event !== "greyguard-event"
            ) {
              continue;
            }

            const securityEvent = JSON.parse(
              message.data,
            ) as SecurityEvent;

            const eventId =
              securityEvent.event_id
              ?? message.id;

            if (
              !eventId
              || seenEventIds.current.has(eventId)
            ) {
              continue;
            }

            seenEventIds.current.add(eventId);

            setEvents((current) =>
              [
                securityEvent,
                ...current,
              ].slice(0, 250),
            );

            setLastEventAt(
              securityEvent.timestamp,
            );
          }
        }

        if (!intentionallyClosed) {
          throw new Error(
            "The live connection closed unexpectedly.",
          );
        }
      } catch (error) {
        if (
          controller.signal.aborted
          || intentionallyClosed
        ) {
          return;
        }

        const message =
          error instanceof Error
            ? error.message
            : "Unable to connect to GreyGuard.";

        setConnectionStatus("RECONNECTING");
        setConnectionError(message);

        reconnectTimer = setTimeout(() => {
          setConnectionAttempt(
            (current) => current + 1,
          );
        }, 2500);
      }
    }

    void connect();

    return () => {
      intentionallyClosed = true;
      controller.abort();

      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
    };
  }, [
    paused,
    eventType,
    agentFilter,
    connectionAttempt,
  ]);

  const filteredEvents = useMemo(() => {
    const normalizedSearch =
      searchText.trim().toLowerCase();

    return events.filter((event) => {
      const eventSeverity =
        severityOrder[event.severity] ?? 0;
      const requiredSeverity =
        severityOrder[minimumSeverity] ?? 0;

      if (eventSeverity < requiredSeverity) {
        return false;
      }

      if (!normalizedSearch) {
        return true;
      }

      const searchable = [
        event.event_id,
        event.event_type,
        event.agent_name,
        event.action,
        event.outcome,
        event.actor,
        event.summary,
        event.request_id,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return searchable.includes(normalizedSearch);
    });
  }, [
    events,
    minimumSeverity,
    searchText,
  ]);

  const statistics = useMemo(() => {
    const uniqueAgents = new Set(
      events
        .map((event) => event.agent_name)
        .filter(Boolean),
    );

    return {
      total: events.length,
      highRisk: events.filter(
        (event) =>
          event.severity === "HIGH"
          || event.severity === "CRITICAL",
      ).length,
      denials: events.filter(
        (event) =>
          event.outcome.includes("DENIED")
          || event.outcome === "BLOCK"
          || event.outcome === "REFUSED",
      ).length,
      agents: uniqueAgents.size,
    };
  }, [events]);

  function reconnect() {
    seenEventIds.current.clear();
    setConnectionStatus("RECONNECTING");
    setConnectionAttempt(
      (current) => current + 1,
    );
  }

  function clearFeed() {
    setEvents([]);
    seenEventIds.current.clear();
    setExpandedEvent(null);
    setLastEventAt(null);
  }

  return (
    <main className="live-page">
      <div className="live-page__atmosphere">
        <span className="live-orbit live-orbit--one" />
        <span className="live-orbit live-orbit--two" />
        <span className="live-scan-beam" />
        <span className="live-grid-glow" />
      </div>

      <section className="live-hero">
        <div className="live-hero__copy">
          <div className="live-eyebrow">
            <Signal size={15} />
            Continuous control-plane telemetry
          </div>

          <h1>Live Operations Center</h1>

          <p>
            Observe policy decisions, authentication,
            approvals and controlled execution evidence
            as GreyGuard records them.
          </p>
        </div>

        <div
          className={[
            "live-connection",
            `live-connection--${connectionStatus.toLowerCase()}`,
          ].join(" ")}
        >
          <span className="live-connection__pulse" />

          <div>
            <strong>
              {connectionLabel(connectionStatus)}
            </strong>

            <small>
              {connectionError
                || (
                  lastEventAt
                    ? `Last evidence ${formatTimestamp(lastEventAt)}`
                    : "Waiting for security evidence"
                )}
            </small>
          </div>

          {connectionStatus === "CONNECTED" ? (
            <ShieldCheck size={22} />
          ) : connectionStatus === "PAUSED" ? (
            <CirclePause size={22} />
          ) : (
            <WifiOff size={22} />
          )}
        </div>
      </section>

      <section className="live-metrics">
        <article className="live-metric">
          <span className="live-metric__icon">
            <Activity size={21} />
          </span>
          <div>
            <small>Captured events</small>
            <strong>{statistics.total}</strong>
          </div>
          <em>Current session</em>
        </article>

        <article className="live-metric">
          <span className="live-metric__icon live-metric__icon--danger">
            <AlertTriangle size={21} />
          </span>
          <div>
            <small>High-risk signals</small>
            <strong>{statistics.highRisk}</strong>
          </div>
          <em>High + critical</em>
        </article>

        <article className="live-metric">
          <span className="live-metric__icon live-metric__icon--warning">
            <XCircle size={21} />
          </span>
          <div>
            <small>Denied activity</small>
            <strong>{statistics.denials}</strong>
          </div>
          <em>Denied, blocked, refused</em>
        </article>

        <article className="live-metric">
          <span className="live-metric__icon live-metric__icon--agent">
            <Bot size={21} />
          </span>
          <div>
            <small>Observed agents</small>
            <strong>{statistics.agents}</strong>
          </div>
          <em>Connected evidence sources</em>
        </article>
      </section>

      <section className="live-control-panel">
        <div className="live-control-panel__heading">
          <div>
            <span>
              <Filter size={16} />
              Stream controls
            </span>
            <h2>Operational event feed</h2>
          </div>

          <div className="live-control-panel__actions">
            <button
              type="button"
              className="live-button live-button--ghost"
              onClick={clearFeed}
            >
              <Eraser size={17} />
              Clear view
            </button>

            <button
              type="button"
              className="live-button live-button--ghost"
              onClick={reconnect}
              disabled={paused}
            >
              <RefreshCw size={17} />
              Reconnect
            </button>

            <button
              type="button"
              className="live-button live-button--primary"
              onClick={() =>
                setPaused((current) => !current)
              }
            >
              {paused ? (
                <>
                  <CirclePlay size={18} />
                  Resume monitoring
                </>
              ) : (
                <>
                  <CirclePause size={18} />
                  Pause monitoring
                </>
              )}
            </button>
          </div>
        </div>

        <div className="live-filters">
          <label>
            <span>Event type</span>
            <select
              value={eventType}
              onChange={(event) =>
                setEventType(event.target.value)
              }
            >
              {eventTypes.map((type) => (
                <option
                  key={type}
                  value={type}
                >
                  {type === "ALL"
                    ? "All event types"
                    : type}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Minimum severity</span>
            <select
              value={minimumSeverity}
              onChange={(event) =>
                setMinimumSeverity(
                  event.target.value,
                )
              }
            >
              {[
                "INFO",
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
              ].map((severity) => (
                <option
                  key={severity}
                  value={severity}
                >
                  {severity}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Agent name</span>
            <div className="live-input">
              <Bot size={16} />
              <input
                value={agentFilter}
                onChange={(event) =>
                  setAgentFilter(
                    event.target.value,
                  )
                }
                placeholder="All agents"
              />
            </div>
          </label>

          <label>
            <span>Search evidence</span>
            <div className="live-input">
              <Search size={16} />
              <input
                value={searchText}
                onChange={(event) =>
                  setSearchText(
                    event.target.value,
                  )
                }
                placeholder="Action, outcome or ID"
              />
            </div>
          </label>
        </div>
      </section>

      <section className="live-feed">
        <header className="live-feed__header">
          <div>
            <span className="live-feed__indicator">
              <span />
              Evidence stream
            </span>

            <h2>Security activity timeline</h2>
          </div>

          <p>
            Showing {filteredEvents.length} of{" "}
            {events.length} captured events
          </p>
        </header>

        {connectionStatus === "ERROR"
        && events.length === 0 ? (
          <div className="live-state live-state--error">
            <ShieldAlert size={34} />
            <h3>Live monitoring unavailable</h3>
            <p>{connectionError}</p>
            <button
              type="button"
              className="live-button live-button--primary"
              onClick={reconnect}
            >
              <RefreshCw size={17} />
              Try again
            </button>
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="live-state">
            <Radio size={34} />
            <h3>Waiting for matching activity</h3>
            <p>
              GreyGuard is listening for policy,
              authentication, approval and execution
              evidence.
            </p>
          </div>
        ) : (
          <div className="live-timeline">
            {filteredEvents.map((event) => {
              const EventIcon = eventIcon(
                event.event_type,
              );
              const expanded =
                expandedEvent === event.event_id;

              return (
                <article
                  key={event.event_id}
                  className={[
                    "live-event",
                    expanded
                      ? "live-event--expanded"
                      : "",
                  ].join(" ")}
                >
                  <div className="live-event__rail">
                    <span>
                      <EventIcon size={17} />
                    </span>
                  </div>

                  <button
                    type="button"
                    className="live-event__summary"
                    onClick={() =>
                      setExpandedEvent(
                        expanded
                          ? null
                          : event.event_id,
                      )
                    }
                    aria-expanded={expanded}
                  >
                    <div className="live-event__main">
                      <div className="live-event__badges">
                        <span className="live-type">
                          {event.event_type}
                        </span>

                        <span
                          className={severityClass(
                            event.severity,
                          )}
                        >
                          {event.severity}
                        </span>

                        <span className="live-outcome">
                          {event.outcome}
                        </span>
                      </div>

                      <h3>{event.summary}</h3>

                      <div className="live-event__metadata">
                        <span>
                          <Bot size={14} />
                          {event.agent_name
                            || "System"}
                        </span>

                        <span>
                          <Activity size={14} />
                          {event.action
                            || "No action"}
                        </span>

                        <span>
                          <Clock3 size={14} />
                          {formatTimestamp(
                            event.timestamp,
                          )}
                        </span>
                      </div>
                    </div>

                    {expanded ? (
                      <ChevronUp size={19} />
                    ) : (
                      <ChevronDown size={19} />
                    )}
                  </button>

                  {expanded && (
                    <div className="live-event__details">
                      <dl>
                        <div>
                          <dt>Event ID</dt>
                          <dd>{event.event_id}</dd>
                        </div>

                        <div>
                          <dt>Request ID</dt>
                          <dd>
                            {event.request_id
                              || "Not linked"}
                          </dd>
                        </div>

                        <div>
                          <dt>Actor</dt>
                          <dd>
                            {event.actor
                              || "System"}
                          </dd>
                        </div>

                        <div>
                          <dt>Recorded</dt>
                          <dd>
                            {formatTimestamp(
                              event.timestamp,
                            )}
                          </dd>
                        </div>
                      </dl>

                      <div className="live-event__payload">
                        <strong>Evidence details</strong>
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
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
