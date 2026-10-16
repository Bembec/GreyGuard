import { useShowMore } from "../components/page/ShowMore";
import { StatCard, StatGrid } from "../components/page/StatCard"
import { Guidance } from "../components/page/Guidance"
import { PageHeader } from "../components/page/PageHeader"
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock3,
  Eye,
  FileText,
  Fingerprint,
  Gavel,
  RefreshCw,
  Search,
  ShieldCheck,
  ShieldX,
  UserCheck,
  X,
  CheckSquare,
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
import { useDismissableLayer } from "../hooks/useDismissableLayer";
import { usePermission } from "../hooks/usePermission";
import "../styles/approvals.css";


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
};

type ApprovalDecision = {
  requestId: string;
  decision: "APPROVED" | "DENIED";
  note: string;
};

type ApiError = {
  detail?: string;
};

type ViewMode =
  | "PENDING"
  | "RESOLVED"
  | "ALL";

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

async function fetchApprovalRequests():
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

async function submitDecision(
  input: ApprovalDecision,
): Promise<unknown> {
  const response = await fetch(
    `${API_BASE_URL}/tool-requests/${
      encodeURIComponent(input.requestId)
    }/decision`,
    {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify({
        decision: input.decision,
        note: input.note.trim() || null,
      }),
    },
  );

  return readResponse<unknown>(response);
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

function readable(value: string) {
  return value.replaceAll("_", " ");
}

function statusClass(value: string) {
  return value
    .toLowerCase()
    .replaceAll("_", "-");
}

function riskLevel(score: number) {
  if (score >= 100) {
    return "CRITICAL";
  }

  if (score >= 60) {
    return "HIGH";
  }

  if (score >= 20) {
    return "MEDIUM";
  }

  return "LOW";
}

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  // POST /tool-requests/{id}/decision requires approval:manage server-side
  // (admin_auth.py's required_permission) - PLATFORM_ADMIN and SECURITY_ANALYST hold it,
  // AUDITOR (read-only) does not.
  const canDecide = usePermission({ permission: "approval:manage" });

  const [viewMode, setViewMode] =
    useState<ViewMode>("PENDING");
  const [searchText, setSearchText] =
    useState("");
  const [selectedRequestId, setSelectedRequestId] =
    useState<string | null>(null);
  const [reviewDecision, setReviewDecision] =
    useState<"APPROVED" | "DENIED" | null>(
      null,
    );
  const [reviewNote, setReviewNote] =
    useState("");
  const [notice, setNotice] =
    useState<string | null>(null);

  const requestsQuery = useQuery({
    queryKey: ["approval-requests"],
    queryFn: fetchApprovalRequests,
    refetchInterval: 15_000,
  });

  const approvalRequests = useMemo(
    () => (
      requestsQuery.data?.requests ?? []
    ).filter(
      (request) =>
        request.policy_decision === "ASK",
    ),
    [requestsQuery.data],
  );

  const pendingRequests = approvalRequests.filter(
    (request) =>
      request.approval_status === "PENDING",
  );

  const approvedRequests = approvalRequests.filter(
    (request) =>
      request.approval_status === "APPROVED",
  );

  const deniedRequests = approvalRequests.filter(
    (request) =>
      request.approval_status === "DENIED",
  );

  const selectedRequest =
    approvalRequests.find(
      (request) =>
        request.request_id === selectedRequestId,
    ) ?? null;

  const visibleRequests = useMemo(() => {
    const normalizedSearch =
      searchText.trim().toLowerCase();

    return approvalRequests.filter((request) => {
      const matchesView =
        viewMode === "ALL"
        || (
          viewMode === "PENDING"
          && request.approval_status === "PENDING"
        )
        || (
          viewMode === "RESOLVED"
          && request.approval_status !== "PENDING"
        );

      const searchableText = [
        request.request_id,
        request.agent_name,
        request.action,
        request.target,
      ]
        .join(" ")
        .toLowerCase();

      return (
        matchesView
        && (
          !normalizedSearch
          || searchableText.includes(
            normalizedSearch,
          )
        )
      );
    });
  }, [
    approvalRequests,
    searchText,
    viewMode,
  ]);
  const more = useShowMore(visibleRequests, `${viewMode}|${searchText}`);

  const decisionMutation = useMutation({
    mutationFn: submitDecision,
    onSuccess: async (
      _result,
      variables,
    ) => {
      setNotice(
        variables.decision === "APPROVED"
          ? (
            "Request approved and controlled "
            + "execution completed."
          )
          : "Request denied successfully.",
      );

      setReviewDecision(null);
      setReviewNote("");
      setSelectedRequestId(null);

      await queryClient.invalidateQueries({
        queryKey: ["approval-requests"],
      });

      await queryClient.invalidateQueries({
        queryKey: ["tool-requests"],
      });
    },
    onError: (error: Error) => {
      setNotice(error.message);
    },
  });

  function beginReview(
    request: ToolRequest,
    decision: "APPROVED" | "DENIED",
  ) {
    setSelectedRequestId(request.request_id);
    setReviewDecision(decision);
    setReviewNote("");
  }

  function closeReview() {
    if (decisionMutation.isPending) {
      return;
    }

    setReviewDecision(null);
    setReviewNote("");
  }

  const reviewCancelRef = useRef<HTMLButtonElement>(null);
  const reviewDialogRef = useDismissableLayer<HTMLElement>({
    open: reviewDecision !== null && !!selectedRequest,
    onClose: closeReview,
    trapFocus: true,
    initialFocusRef: reviewCancelRef,
    disabled: decisionMutation.isPending,
    lockBodyScroll: true,
  });

  function submitReview() {
    if (
      !selectedRequest
      || !reviewDecision
    ) {
      return;
    }

    decisionMutation.mutate({
      requestId: selectedRequest.request_id,
      decision: reviewDecision,
      note: reviewNote,
    });
  }

  return (
    <main className="approvals-page gg-page-pad">
      <div
        className="approval-background"
        aria-hidden="true"
      >
        <span className="approval-ring ring-one" />
        <span className="approval-ring ring-two" />
        <span className="approval-ring ring-three" />
        <Fingerprint size={260} />
      </div>

      <PageHeader
        title="Approvals"
        icon={<CheckSquare size={22} />}
        description="Requests that policy marked ASK wait here, paused, until a person decides. Every approval or denial is bound to the reviewer, the time, a note and a permanent security record."
        actions={<button type="button" className="gg-button" onClick={() => void requestsQuery.refetch()} disabled={requestsQuery.isFetching}><RefreshCw size={16} aria-hidden="true" className={requestsQuery.isFetching ? "spin" : undefined} />Refresh queue</button>}
      />

      <Guidance id="approvals" title="How to review a request">
        <ol>
          <li>Open a pending request to see the agent, the action, its target, the payload and the risk it would add.</li>
          <li><strong>Approve</strong> only if the action is expected and in scope; otherwise <strong>deny</strong>. Add a note either way: it becomes part of the evidence.</li>
          <li>An approved request runs in the controlled sandbox. A denied request never executes.</li>
        </ol>
      </Guidance>

      <StatGrid label="Approval summary">
        <StatCard label="Pending review" value={pendingRequests.length} hint="Execution remains paused" tone="warning" icon={<Clock3 size={16} />} />
        <StatCard label="Approved" value={approvedRequests.length} hint="Authorized by an administrator" tone="success" icon={<CheckCircle2 size={16} />} />
        <StatCard label="Denied" value={deniedRequests.length} hint="Prevented before execution" tone="danger" icon={<ShieldX size={16} />} />
        <StatCard label="Total decisions" value={approvedRequests.length + deniedRequests.length} hint="Resolved human reviews" tone="info" icon={<Gavel size={16} />} />
      </StatGrid>

      {notice && (
        <div className="approval-notice">
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

      <section className="approval-workspace">
        <div className="approval-queue-panel">
          <div className="approval-toolbar">
            <div className="approval-tabs">
              <button
                type="button"
                className={
                  viewMode === "PENDING"
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setViewMode("PENDING")
                }
              >
                Pending
                <span>
                  {pendingRequests.length}
                </span>
              </button>

              <button
                type="button"
                className={
                  viewMode === "RESOLVED"
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setViewMode("RESOLVED")
                }
              >
                Resolved
                <span>
                  {
                    approvedRequests.length
                    + deniedRequests.length
                  }
                </span>
              </button>

              <button
                type="button"
                className={
                  viewMode === "ALL"
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setViewMode("ALL")
                }
              >
                All
                <span>
                  {approvalRequests.length}
                </span>
              </button>
            </div>

            <label className="approval-search">
              <Search size={16} />

              <input
                type="search"
                value={searchText}
                onChange={(event) =>
                  setSearchText(event.target.value)
                }
                placeholder={
                  "Search approval queue..."
                }
              />
            </label>
          </div>

          {requestsQuery.isLoading && (
            <LoadingState label="Loading approval queue" rows={4} />
          )}

          {requestsQuery.isError && (
            <ErrorState message={(requestsQuery.error as Error).message} onRetry={() => void requestsQuery.refetch()} />
          )}

          {!requestsQuery.isLoading
            && !requestsQuery.isError
            && (
              <div className="approval-list">
                {more.visible.map(
                  (request) => (
                    <article
                      key={request.request_id}
                      className={
                        `approval-card ${
                          request.approval_status
                            .toLowerCase()
                        }`
                      }
                    >
                      <div className="approval-card-top">
                        <div className="approval-agent">
                          <div>
                            {
                              request.agent_name
                                .charAt(0)
                                .toUpperCase()
                            }
                          </div>

                          <span>
                            <strong>
                              {request.agent_name}
                            </strong>
                            <small>
                              {
                                formatDate(
                                  request.timestamp,
                                )
                              }
                            </small>
                          </span>
                        </div>

                        <span
                          className={
                            `approval-status ${
                              statusClass(
                                request.approval_status,
                              )
                            }`
                          }
                        >
                          {
                            readable(
                              request.approval_status,
                            )
                          }
                        </span>
                      </div>

                      <div className="approval-action">
                        <span>Requested action</span>
                        <strong>
                          {request.action}
                        </strong>
                        <code>
                          {request.target}
                        </code>
                      </div>

                      <div className="approval-card-data">
                        <span>
                          Risk
                          <strong
                            className={
                              `approval-risk ${
                                riskLevel(
                                  request.risk_score,
                                ).toLowerCase()
                              }`
                            }
                          >
                            {request.risk_score}
                            {" · "}
                            {
                              riskLevel(
                                request.risk_score,
                              )
                            }
                          </strong>
                        </span>

                        <span>
                          Risk added
                          <strong>
                            +{request.risk_added}
                          </strong>
                        </span>

                        <span>
                          Execution
                          <strong>
                            {
                              readable(
                                request
                                  .execution_status,
                              )
                            }
                          </strong>
                        </span>
                      </div>

                      <div className="approval-card-actions">
                        <button
                          type="button"
                          className="inspect-approval"
                          onClick={() =>
                            setSelectedRequestId(
                              request.request_id,
                            )
                          }
                        >
                          <Eye size={16} />
                          Inspect
                        </button>

                        {request.approval_status
                          === "PENDING"
                          && canDecide && (
                          <>
                            <button
                              type="button"
                              className="deny-approval"
                              onClick={() =>
                                beginReview(
                                  request,
                                  "DENIED",
                                )
                              }
                            >
                              <ShieldX size={16} />
                              Deny
                            </button>

                            <button
                              type="button"
                              className="approve-approval"
                              onClick={() =>
                                beginReview(
                                  request,
                                  "APPROVED",
                                )
                              }
                            >
                              <Check size={16} />
                              Approve
                            </button>
                          </>
                        )}
                      </div>
                    </article>
                  ),
                )}{more.control}

                {visibleRequests.length === 0 && (
                  <div className="approval-empty">
                    <div className="empty-authority-ring">
                      <ShieldCheck size={30} />
                    </div>

                    <strong>
                      {viewMode === "PENDING"
                        ? "Approval queue is clear"
                        : "No matching reviews"}
                    </strong>

                    <span>
                      {viewMode === "PENDING"
                        ? (
                          "No sensitive action is "
                          + "waiting for authorization."
                        )
                        : (
                          "Change the current view "
                          + "or search."
                        )}
                    </span>
                  </div>
                )}
              </div>
            )}
        </div>

        <aside className="approval-detail-panel">
          {!selectedRequest ? (
            <div className="approval-detail-empty">
              <div className="authority-orbit">
                <UserCheck size={35} />
              </div>

              <strong>
                Human judgment required
              </strong>

              <p>
                Inspect an approval to understand the
                requesting agent, intended target,
                payload, accumulated risk, and
                execution consequences.
              </p>
            </div>
          ) : (
            <>
              <div className="approval-detail-header">
                <div>
                  <span>Approval evidence</span>
                  <h2>
                    {selectedRequest.action}
                  </h2>
                </div>

                <button
                  type="button"
                  aria-label="Close approval details"
                  onClick={() =>
                    setSelectedRequestId(null)
                  }
                >
                  <X size={18} />
                </button>
              </div>

              <div className="approval-detail-grid">
                <div>
                  <span>Agent identity</span>
                  <strong>
                    {selectedRequest.agent_name}
                  </strong>
                </div>

                <div>
                  <span>Risk posture</span>
                  <strong>
                    {selectedRequest.risk_score}
                    {" · "}
                    {
                      riskLevel(
                        selectedRequest.risk_score,
                      )
                    }
                  </strong>
                </div>

                <div>
                  <span>Approval</span>
                  <strong>
                    {
                      readable(
                        selectedRequest
                          .approval_status,
                      )
                    }
                  </strong>
                </div>

                <div>
                  <span>Execution</span>
                  <strong>
                    {
                      readable(
                        selectedRequest
                          .execution_status,
                      )
                    }
                  </strong>
                </div>
              </div>

              <div className="approval-target">
                <span>Requested target</span>
                <code>
                  {selectedRequest.target}
                </code>
              </div>

              <div className="approval-context">
                <div>
                  <FileText size={17} />
                  <span>
                    <strong>Request context</strong>
                    <small>
                      Submitted{" "}
                      {
                        formatDate(
                          selectedRequest.timestamp,
                        )
                      }
                    </small>
                  </span>
                </div>

                <pre>
                  {
                    JSON.stringify(
                      selectedRequest.payload,
                      null,
                      2,
                    )
                  }
                </pre>
              </div>

              {selectedRequest.result && (
                <div className="approval-context">
                  <div>
                    <ShieldCheck size={17} />
                    <span>
                      <strong>
                        Execution evidence
                      </strong>
                      <small>
                        Persistent gateway result
                      </small>
                    </span>
                  </div>

                  <pre>
                    {
                      JSON.stringify(
                        selectedRequest.result,
                        null,
                        2,
                      )
                    }
                  </pre>
                </div>
              )}

              {selectedRequest.approval_status
                === "PENDING" && (
                canDecide ? (
                  <div className="detail-review-actions">
                    <button
                      type="button"
                      className="deny-approval"
                      onClick={() =>
                        beginReview(
                          selectedRequest,
                          "DENIED",
                        )
                      }
                    >
                      <ShieldX size={16} />
                      Deny request
                    </button>

                    <button
                      type="button"
                      className="approve-approval"
                      onClick={() =>
                        beginReview(
                          selectedRequest,
                          "APPROVED",
                        )
                      }
                    >
                      <Check size={16} />
                      Approve request
                    </button>
                  </div>
                ) : (
                  <p className="gg-readonly-note">
                    Your role has read-only access to this queue. Approval or
                    denial requires the Security Analyst or Platform
                    Administrator role.
                  </p>
                )
              )}
            </>
          )}
        </aside>
      </section>

      {reviewDecision && selectedRequest && (
        <div className="review-modal-backdrop">
          <section
            ref={reviewDialogRef}
            className={
              `review-modal ${
                reviewDecision.toLowerCase()
              }`
            }
            role="dialog"
            aria-modal="true"
            aria-labelledby="review-title"
          >
            <div className="review-modal-icon">
              {reviewDecision === "APPROVED" ? (
                <CheckCircle2 size={28} />
              ) : (
                <ShieldX size={28} />
              )}
            </div>

            <span>Human approval decision</span>

            <h2 id="review-title">
              {reviewDecision === "APPROVED"
                ? "Authorize this action?"
                : "Deny this action?"}
            </h2>

            <p>
              <strong>
                {selectedRequest.agent_name}
              </strong>
              {" requested "}
              <strong>
                {selectedRequest.action}
              </strong>
              {" on "}
              <code>
                {selectedRequest.target}
              </code>
              .
            </p>

            {reviewDecision === "APPROVED" && (
              <div className="execution-warning">
                <AlertTriangle size={18} />
                Approval may immediately execute the
                controlled action inside GreyGuard's
                restricted sandbox.
              </div>
            )}

            <label className="review-note">
              Reviewer note
              <textarea
                value={reviewNote}
                onChange={(event) =>
                  setReviewNote(event.target.value)
                }
                maxLength={1000}
                placeholder={
                  reviewDecision === "APPROVED"
                    ? (
                      "Why is this action safe "
                      + "and necessary?"
                    )
                    : (
                      "Why should this request "
                      + "remain blocked?"
                    )
                }
              />
              <small>
                {reviewNote.length} / 1000
              </small>
            </label>

            <div className="review-modal-actions">
              <button
                ref={reviewCancelRef}
                type="button"
                className="cancel-review"
                onClick={closeReview}
                disabled={
                  decisionMutation.isPending
                }
              >
                Cancel
              </button>

              <button
                type="button"
                className={
                  reviewDecision === "APPROVED"
                    ? "confirm-approve"
                    : "confirm-deny"
                }
                onClick={submitReview}
                disabled={
                  decisionMutation.isPending
                }
              >
                {decisionMutation.isPending
                  ? "Recording decision..."
                  : (
                    reviewDecision === "APPROVED"
                      ? "Confirm approval"
                      : "Confirm denial"
                  )}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
