"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { badgeClass, formatLabel } from "@/lib/format";
import { useCurrentUser } from "@/lib/current-user-context";
import PhasePipeline from "@/components/PhasePipeline";
import type { ArtefactVersion, Project, ReviewDecision, Run, RunHistoryEntry } from "@/lib/types";

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
  const { currentUserId, currentUser } = useCurrentUser();

  const [project, setProject] = useState<Project | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [activeTaskRequest, setActiveTaskRequest] = useState<string | null>(null);
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
            setActiveTaskRequest(resumable.task_request);
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

  async function handleStartRun(e: React.FormEvent) {
    e.preventDefault();
    if (!taskRequest.trim()) return;

    setStartingRun(true);
    setRunError(null);
    try {
      const submittedTask = taskRequest.trim();
      const startedRun = await api.startRun(projectId, submittedTask);
      setRun(startedRun);
      setActiveTaskRequest(submittedTask);
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
    if (!run || !currentUserId) return;

    setSubmittingReview(true);
    setReviewError(null);
    try {
      const commentList = comments
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const updatedProject = await api.submitReview(run.id, currentUserId, decision, commentList);
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
    <main className="page page-wide stack">
      <div>
        <Link href="/" className="muted">
          ← Projects
        </Link>
      </div>

      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>{project.name}</h2>
          <span className={badgeClass(project.status)}>{formatLabel(project.status)}</span>
        </div>
        <p className="muted" style={{ marginBottom: "1.1rem" }}>
          Phase: {formatLabel(project.current_phase)} — {formatLabel(project.phase_status)}
        </p>
        <PhasePipeline
          currentPhase={project.current_phase}
          phaseStatus={project.phase_status}
          projectStatus={project.status}
        />
      </section>

      {project.status === "completed" && (
        <section className="card">
          <p>🎉 This project has completed its full lifecycle.</p>
        </section>
      )}

      {canStartRun && project.status !== "completed" && (
        <section className="card">
          <div className="section-title">Start a run for {formatLabel(project.current_phase)}</div>
          {currentUser && (
            <p className="muted" style={{ marginBottom: "0.75rem" }}>
              Running as <strong>{currentUser.email}</strong> ({currentUser.role})
            </p>
          )}
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
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="section-title" style={{ marginBottom: 0 }}>
              {formatLabel(run.phase)} — run #{run.run_number}
            </div>
            <span className={badgeClass(run.state)}>{formatLabel(run.state)}</span>
          </div>
          <p className="muted" style={{ marginTop: "0.3rem" }}>
            Agent: {run.agent_id}
          </p>

          {activeTaskRequest && <div className="task-note" style={{ marginTop: "0.75rem" }}>{activeTaskRequest}</div>}

          {artefactVersions.length > 0 && (
            <ul className="stack" style={{ listStyle: "none", padding: 0, marginTop: "0.9rem" }}>
              {artefactVersions.map((version) => (
                <li key={version.id} className="row" style={{ justifyContent: "space-between" }}>
                  <span>
                    {formatLabel(version.artefact_type)} — {version.version_label}{" "}
                    <span className={badgeClass(version.status)}>{formatLabel(version.status)}</span>
                  </span>
                  <a href={api.downloadUrlForVersion(version.id)}>Download</a>
                </li>
              ))}
            </ul>
          )}

          {awaitingReview && (
            <form onSubmit={handleSubmitReview} className="stack" style={{ marginTop: "1.1rem" }}>
              <div className="divider" style={{ marginBottom: "0.5rem" }} />
              <div className="section-title" style={{ marginBottom: "0.25rem" }}>
                Submit review
              </div>
              {currentUser ? (
                <p className="muted">
                  Reviewing as <strong>{currentUser.email}</strong> ({currentUser.role}) — switch who you&apos;re
                  acting as in the header if needed.
                </p>
              ) : (
                <p className="error">No user selected — add one in the header first.</p>
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
              <button type="submit" disabled={submittingReview || !currentUserId}>
                {submittingReview ? "Submitting…" : "Submit review"}
              </button>
            </form>
          )}
        </section>
      )}

      <section className="card">
        <div className="section-title">Run history</div>
        {historyError && <p className="error">{historyError}</p>}
        {runHistory.length === 0 ? (
          <p className="muted">No runs yet for this project.</p>
        ) : (
          <ul className="stack" style={{ listStyle: "none", padding: 0 }}>
            {runHistory.map((entry) => (
              <li key={entry.id} style={{ borderTop: "1px solid var(--border)", paddingTop: "0.6rem" }}>
                <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                  <div className="row">
                    <strong>
                      {formatLabel(entry.phase)} #{entry.run_number}
                    </strong>
                    <span className={badgeClass(entry.state)}>{formatLabel(entry.state)}</span>
                    {entry.review_decision && (
                      <span className={badgeClass(entry.review_decision)}>{formatLabel(entry.review_decision)}</span>
                    )}
                  </div>
                  <button type="button" className="secondary" onClick={() => handleToggleHistoryRun(entry.id)}>
                    {expandedHistoryRunId === entry.id ? "Hide" : "Details"}
                  </button>
                </div>
                {entry.task_request && (
                  <p className="muted" style={{ marginTop: "0.3rem" }}>
                    {entry.task_request}
                  </p>
                )}
                {expandedHistoryRunId === entry.id && (
                  <div style={{ marginTop: "0.5rem" }}>
                    {expandedHistoryLoading ? (
                      <p className="muted">Loading…</p>
                    ) : expandedHistoryVersions.length === 0 ? (
                      <p className="muted">No artefacts produced by this run.</p>
                    ) : (
                      <ul style={{ listStyle: "none", padding: 0 }}>
                        {expandedHistoryVersions.map((version) => (
                          <li key={version.id} className="row" style={{ justifyContent: "space-between" }}>
                            <span>
                              {formatLabel(version.artefact_type)} — {version.version_label}{" "}
                              <span className={badgeClass(version.status)}>{formatLabel(version.status)}</span>
                            </span>
                            <a href={api.downloadUrlForVersion(version.id)}>Download</a>
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
