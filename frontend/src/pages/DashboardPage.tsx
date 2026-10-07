import {
  Activity,
  Bot,
  CheckCircle2,
  Clock3,
  LockKeyhole,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react"

import { useAuth } from "../context/AuthContext"
import "../styles/pages.css"

export function DashboardPage() {
  const { agents } = useAuth()

  const activeAgents = agents.filter(
    (agent) => agent.agent_status === "ACTIVE",
  ).length

  const suspendedAgents = agents.filter(
    (agent) =>
      agent.agent_status === "SUSPENDED",
  ).length

  const highRiskAgents = agents.filter(
    (agent) =>
      agent.risk_level === "HIGH"
      || agent.risk_level === "CRITICAL",
  ).length

  return (
    <section className="page">
      <header className="page-heading">
        <div>
          <p className="page-heading__eyebrow">
            Live security posture
          </p>

          <h1>
            Good afternoon,
            <span> Administrator.</span>
          </h1>

          <p>
            GreyGuard is monitoring identity,
            permission, risk and controlled execution
            across your registered agents.
          </p>
        </div>

        <div className="page-heading__status">
          <span />
          Control plane protected
        </div>
      </header>

      <div className="metric-grid">
        <article className="metric-card metric-card--cyan">
          <div className="metric-card__icon">
            <Bot size={22} />
          </div>

          <div>
            <span>Registered agents</span>
            <strong>{agents.length}</strong>
            <small>
              {activeAgents} currently active
            </small>
          </div>
        </article>

        <article className="metric-card metric-card--green">
          <div className="metric-card__icon">
            <ShieldCheck size={22} />
          </div>

          <div>
            <span>Active agents</span>
            <strong>{activeAgents}</strong>
            <small>Operating within policy</small>
          </div>
        </article>

        <article className="metric-card metric-card--amber">
          <div className="metric-card__icon">
            <ShieldAlert size={22} />
          </div>

          <div>
            <span>High-risk agents</span>
            <strong>{highRiskAgents}</strong>
            <small>Requires closer review</small>
          </div>
        </article>

        <article className="metric-card metric-card--red">
          <div className="metric-card__icon">
            <LockKeyhole size={22} />
          </div>

          <div>
            <span>Suspended agents</span>
            <strong>{suspendedAgents}</strong>
            <small>Execution access refused</small>
          </div>
        </article>
      </div>

      <div className="dashboard-grid">
        <article className="dashboard-card dashboard-card--posture">
          <div className="dashboard-card__heading">
            <div>
              <p>Containment posture</p>
              <h3>Security boundaries</h3>
            </div>

            <span className="status-chip status-chip--success">
              Enforced
            </span>
          </div>

          <div className="posture-orbit">
            <div className="posture-orbit__ring posture-orbit__ring--outer" />
            <div className="posture-orbit__ring posture-orbit__ring--inner" />

            <div className="posture-orbit__core">
              <ShieldCheck size={34} />
              <strong>Protected</strong>
              <span>Gateway sealed</span>
            </div>

            <span className="posture-node posture-node--one">
              Identity
            </span>
            <span className="posture-node posture-node--two">
              Scope
            </span>
            <span className="posture-node posture-node--three">
              Policy
            </span>
            <span className="posture-node posture-node--four">
              Sandbox
            </span>
          </div>
        </article>

        <article className="dashboard-card">
          <div className="dashboard-card__heading">
            <div>
              <p>Control pipeline</p>
              <h3>Request enforcement</h3>
            </div>

            <Activity size={20} />
          </div>

          <div className="pipeline">
            {[
              ["Identity", "Credential verified"],
              ["Scope", "Action boundary checked"],
              ["Policy", "Decision calculated"],
              ["Approval", "Human gate enforced"],
              ["Execution", "Sandbox evidence stored"],
            ].map(([name, description], index) => (
              <div
                className="pipeline__step"
                key={name}
              >
                <span>
                  {index + 1}
                </span>

                <div>
                  <strong>{name}</strong>
                  <small>{description}</small>
                </div>

                <CheckCircle2 size={17} />
              </div>
            ))}
          </div>
        </article>

        <article className="dashboard-card dashboard-card--wide">
          <div className="dashboard-card__heading">
            <div>
              <p>Registered estate</p>
              <h3>Agent risk overview</h3>
            </div>

            <span className="dashboard-card__updated">
              <Clock3 size={15} />
              Current session
            </span>
          </div>

          <div className="agent-table">
            <div className="agent-table__header">
              <span>Agent</span>
              <span>Status</span>
              <span>Risk</span>
              <span>Score</span>
            </div>

            {agents.slice(0, 6).map((agent) => (
              <div
                className="agent-table__row"
                key={agent.agent_name}
              >
                <span className="agent-name">
                  <span>
                    <Bot size={16} />
                  </span>
                  {agent.agent_name}
                </span>

                <span
                  className={[
                    "status-chip",
                    agent.agent_status === "ACTIVE"
                      ? "status-chip--success"
                      : "status-chip--danger",
                  ].join(" ")}
                >
                  {agent.agent_status}
                </span>

                <span>
                  {agent.risk_level}
                </span>

                <span className="risk-score">
                  <span
                    style={{
                      width: `${Math.min(
                        agent.risk_score,
                        100,
                      )}%`,
                    }}
                  />
                  {agent.risk_score}
                </span>
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  )
}
