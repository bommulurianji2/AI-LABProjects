"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatLabel } from "@/lib/format";
import type { ArtefactVersion, Project, ReviewDecision, Run, RunHistoryEntry, User } from "@/lib/types";

const LAST_REVIEWER_STORAGE_KEY = "pp-sdlc-last-reviewer-id";

const DECISIONS: { value: ReviewDecision; label: string }[] = [
  { value: "approved", label: "Approve" },
  { value: "approved_with_comments", label: "Approve with comments" },
  { value: "rework_required", label: "Request rework" },
  { value: "rejected", label: "Reject" },
];

const RESUMABLE_RUN_STATES = new Set(["waiting_for_human_review", "in_review"]);

export default function ProjectWorkspacePage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [artefactVersions, setArtefactVersions] = useState<ArtefactVersion[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [runHistory, setRunHistory] = useState<RunHistoryEntry[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [expandedHistoryRunId, setExpandedHistoryRunId] = useState<string | null>(null);
  const [expandedHistoryVersions, setExpandedHistoryVersions] = useState<ArtefactVersion[]>([]);
  const [expandedHistoryLoading, setExpandedHistoryLoading] = useState(false);

  const [taskRequest, setTaskRequest] = useState("");
  const [startingRun, setStartingRun] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [users, setUsers] = useState<User[]>([]);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [reviewerId, setReviewerId] = useState("");
  const [showAddReviewer, setShowAddReviewer] = useState(false);
  const [newReviewerEmail, setNewReviewerEmail] = useState("");
  const [newReviewerRole, setNewReviewerRole] = useState("Reviewer");
  const [addingReviewer, setAddingReviewer] = useState(false);
  const [addReviewerError, setAddReviewerError] = useState<string | null>(null);
  const [decision, setDecision] = useState<ReviewDecision>("approved");
  const [comments, setComments] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    // The guard below prevents setState after this component unmounts (or
    // projectId changes again) before the fetch resolves. See
    // https://react.dev/learn/synchronizing-with-effects#fetching-data.
    let ignore = false;
    (async () => {
      try {
        const [projectData, history] = await Promise.all([
          api.getProject(projectId),
          api.listProjectRuns(projectId),
        ]);
        if (ignore) return;
        setProject(projectData);
        setLoadError(null);
        setRunHistory(history);
        setHistoryError(null);

        // Restore an in-flight review after a page refresh: find the most
        // recent run for the project's current phase that's still waiting
        // on a human, and rehydrate it as the active `run` the same way it
        // would look if this page had never been reloaded.
        const resumable = [...history]
          .reverse()
          .find((entry) => entry.phase === projectData.current_phase && RESUMABLE_RUN_STATES.has(entry.state));
        if (resumable) {
          const [resumedRun, versions] = await Promise.all([
            api.getRun(resumable.id),
            api.getRunArtefactVersions(resumable.id),
          ]);
          if (!ignore) {
            setRun(resumedRun);
            setArtefactVersions(versions);
          }
        }
      } catch (err) {
        if (!ignore) {
          setLoadError(err instanceof ApiError ? err.message : "Could not reach the backend.");
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [projectId]);

  useEffect(() => {
    // Reviewers aren't project-scoped, so this loads once per page visit,
    // independent of projectId. Restores the last-used reviewer from this
    // browser (pure convenience for repeated manual testing — not an
    // identity mechanism) so a tester doesn't re-pick themselves every run.
    let ignore = false;
    (async () => {
      try {
        const data = await api.listUsers();
        if (ignore) return;
        setUsers(data);
        setUsersError(null);
        const lastReviewerId = window.localStorage.getItem(LAST_REVIEWER_STORAGE_KEY);
        if (lastReviewerId && data.some((u) => u.id === lastReviewerId)) {
          setReviewerId(lastReviewerId);
        } else if (data.length > 0) {
          setReviewerId(data[0].id);
        }
      } catch (err) {
        if (!ignore) {
          setUsersError(err instanceof ApiError ? err.message : "Could not load reviewers.");
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  async function refreshRunHistory() {
    try {
      setRunHistory(await api.listProjectRuns(projectId));
      setHistoryError(null);
    } catch (err) {
      setHistoryError(err instanceof ApiError ? err.message : "Could not load run history.");
    }
  }

  async function handleToggleHistoryRun(runId: string) {
    if (expandedHistoryRunId === runId) {
      setExpandedHistoryRunId(null);
      setExpandedHistoryVersions([]);
      return;
    }
    setExpandedHistoryRunId(runId);
    setExpandedHistoryLoading(true);
    try {
      setExpandedHistoryVersions(await api.getRunArtefactVersions(runId));
    } catch {
      setExpandedHistoryVersions([]);
    } finally {
      setExpandedHistoryLoading(false);
    }
  }

  async function handleAddReviewer(e: React.FormEvent) {
    e.preventDefault();
    if (!newReviewerEmail.trim()) return;

    setAddingReviewer(true);
    setAddReviewerError(null);
    try {
      const user = await api.createUser(newReviewerEmail.trim(), newReviewerRole.trim() || "Reviewer");
      setUsers((prev) => (prev.some((u) => u.id === user.id) ? prev : [...prev, user]));
      setReviewerId(user.id);
      window.localStorage.setItem(LAST_REVIEWER_STORAGE_KEY, user.id);
      setNewReviewerEmail("");
      setShowAddReviewer(false);
    } catch (err) {
      setAddReviewerError(err instanceof ApiError ? err.message : "Could not add reviewer.");
    } finally {
      setAddingReviewer(false);
    }
  }

  async function handleStartRun(e: React.FormEvent) {
    e.preventDefault();
    if (!taskRequest.trim()) return;

    setStartingRun(true);
    setRunError(null);
    try {
      const startedRun = await api.startRun(projectId, taskRequest.trim());
      setRun(startedRun);
      setTaskRequest("");
      setArtefactVersions(await api.getRunArtefactVersions(startedRun.id));
      setProject(await api.getProject(projectId)); // phase_status just moved to awaiting_review
      await refreshRunHistory();
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Could not start the run.");
    } finally {
      setStartingRun(false);
    }
  }

  async function handleSubmitReview(e: React.FormEvent) {
    e.preventDefault();
    if (!run || !reviewerId.trim()) return;

    setSubmittingReview(true);
    setReviewError(null);
    try {
      const commentList = comments
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const updatedProject = await api.submitReview(run.id, reviewerId.trim(), decision, commentList);
      window.localStorage.setItem(LAST_REVIEWER_STORAGE_KEY, reviewerId.trim());
      setProject(updatedProject);
      setRun(await api.getRun(run.id));
      setArtefactVersions(await api.getRunArtefactVersions(run.id)); // may have just been promoted to baseline
      setComments("");
      await refreshRunHistory();
    } catch (err) {
      setReviewError(err instanceof ApiError ? err.message : "Could not submit the review.");
    } finally {
      setSubmittingReview(false);
    }
  }

  if (loadError) {
    return (
      <main className="page">
        <p className="error">{loadError}</p>
        <Link href="/">Back to projects</Link>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="page">
        <p className="muted">Loading…</p>
      </main>
    );
  }

  // Mirrors the backend's own guard in OrchestratorService.start_run — a
  // run can only start when the phase is actually pending/rework.
  const canStartRun =
    project.status !== "completed" &&
    (project.phase_status === "pending" || project.phase_status === "rework") &&
    (!run || run.state === "completed");
  const awaitingReview = run?.state === "waiting_for_human_review";

  return (
    <main className="page stack">
      <div>
        <Link href="/" className="muted">
          ← Projects
        </Link>
      </div>

      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>{project.name}</h2>
          <span className="badge">{formatLabel(project.status)}</span>
        </div>
        <p className="muted">
          Phase: {formatLabel(project.current_phase)} — {formatLabel(project.phase_status)}
        </p>
      </section>

      {project.status === "completed" && (
        <section className="card">
          <p>This project has completed its full lifecycle.</p>
        </section>
      )}

      {canStartRun && project.status !== "completed" && (
        <section className="card">
          <h3>Start a run for {formatLabel(project.current_phase)}</h3>
          <form onSubmit={handleStartRun} className="stack">
            <div className="field">
              <label htmlFor="task-request">Task request</label>
              <textarea
                id="task-request"
                value={taskRequest}
                onChange={(e) => setTaskRequest(e.target.value)}
                rows={3}
                placeholder="Describe what this agent should work on…"
                disabled={startingRun}
              />
            </div>
            {runError && <p className="error">{runError}</p>}
            <button type="submit" disabled={startingRun || !taskRequest.trim()}>
              {startingRun ? "Running…" : "Start run"}
            </button>
          </form>
        </section>
      )}

      {run && (
        <section className="card">
          <h3>
            Run for {formatLabel(run.phase)} (#{run.run_number})
          </h3>
          <p className="muted">Agent: {run.agent_id}</p>
          <p>
            Status: <span className="badge">{formatLabel(run.state)}</span>
          </p>

          {artefactVersions.length > 0 && (
            <ul className="stack" style={{ listStyle: "none", padding: 0 }}>
              {artefactVersions.map((version) => (
                <li key={version.id}>
                  {formatLabel(version.artefact_type)} — {version.version_label} ({formatLabel(version.status)})
                  {" — "}
                  <a href={api.downloadUrlForVersion(version.id)}>Download</a>
                </li>
              ))}
            </ul>
          )}

          {awaitingReview && (
            <form onSubmit={handleSubmitReview} className="stack" style={{ marginTop: "1rem" }}>
              <h4>Submit review</h4>
              {usersError && <p className="error">{usersError}</p>}
              <div className="field">
                <label htmlFor="reviewer-id">Reviewer</label>
                {users.length > 0 ? (
                  <select
                    id="reviewer-id"
                    value={reviewerId}
                    onChange={(e) => setReviewerId(e.target.value)}
                    disabled={submittingReview}
                  >
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.email} ({u.role})
                      </option>
                    ))}
                  </select>
                ) : (
                  <p className="muted">No reviewers yet — add one below.</p>
                )}
                <button type="button" onClick={() => setShowAddReviewer((v) => !v)} className="secondary">
                  {showAddReviewer ? "Cancel" : "+ Add reviewer"}
                </button>
              </div>

              {showAddReviewer && (
                <div className="field" style={{ border: "1px solid var(--border)", borderRadius: 6, padding: "0.75rem" }}>
                  <div className="field">
                    <label htmlFor="new-reviewer-email">New reviewer email</label>
                    <input
                      id="new-reviewer-email"
                      value={newReviewerEmail}
                      onChange={(e) => setNewReviewerEmail(e.target.value)}
                      placeholder="reviewer@example.test"
                      disabled={addingReviewer}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="new-reviewer-role">Role</label>
                    <input
                      id="new-reviewer-role"
                      value={newReviewerRole}
                      onChange={(e) => setNewReviewerRole(e.target.value)}
                      placeholder="Reviewer"
                      disabled={addingReviewer}
                    />
                  </div>
                  {addReviewerError && <p className="error">{addReviewerError}</p>}
                  <button type="button" onClick={handleAddReviewer} disabled={addingReviewer || !newReviewerEmail.trim()}>
                    {addingReviewer ? "Adding…" : "Add reviewer"}
                  </button>
                </div>
              )}
              <div className="field">
                <label htmlFor="decision">Decision</label>
                <select
                  id="decision"
                  value={decision}
                  onChange={(e) => setDecision(e.target.value as ReviewDecision)}
                  disabled={submittingReview}
                >
                  {DECISIONS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="comments">Comments (one per line, optional)</label>
                <textarea
                  id="comments"
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                  rows={3}
                  disabled={submittingReview}
                />
              </div>
              {reviewError && <p className="error">{reviewError}</p>}
              <button type="submit" disabled={submittingReview || !reviewerId.trim()}>
                {submittingReview ? "Submitting…" : "Submit review"}
              </button>
            </form>
          )}
        </section>
      )}

      <section className="card">
        <h3>Run history</h3>
        {historyError && <p className="error">{historyError}</p>}
        {runHistory.length === 0 ? (
          <p className="muted">No runs yet for this project.</p>
        ) : (
          <ul className="stack" style={{ listStyle: "none", padding: 0 }}>
            {runHistory.map((entry) => (
              <li key={entry.id} style={{ borderTop: "1px solid var(--border)", paddingTop: "0.5rem" }}>
                <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                  <span>
                    {formatLabel(entry.phase)} (#{entry.run_number}) — <span className="badge">{formatLabel(entry.state)}</span>
                    {entry.review_decision && (
                      <>
                        {" "}
                        — <span className="badge">{formatLabel(entry.review_decision)}</span>
                      </>
                    )}
                  </span>
                  <button type="button" className="secondary" onClick={() => handleToggleHistoryRun(entry.id)}>
                    {expandedHistoryRunId === entry.id ? "Hide" : "Details"}
                  </button>
                </div>
                {expandedHistoryRunId === entry.id && (
                  <div style={{ marginTop: "0.5rem" }}>
                    {expandedHistoryLoading ? (
                      <p className="muted">Loading…</p>
                    ) : expandedHistoryVersions.length === 0 ? (
                      <p className="muted">No artefacts produced by this run.</p>
                    ) : (
                      <ul style={{ listStyle: "none", padding: 0 }}>
                        {expandedHistoryVersions.map((version) => (
                          <li key={version.id}>
                            {formatLabel(version.artefact_type)} — {version.version_label} (
                            {formatLabel(version.status)}) — <a href={api.downloadUrlForVersion(version.id)}>Download</a>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
