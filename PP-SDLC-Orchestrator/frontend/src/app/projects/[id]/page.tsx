"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatLabel } from "@/lib/format";
import type { ArtefactVersion, Project, ReviewDecision, Run } from "@/lib/types";

const DECISIONS: { value: ReviewDecision; label: string }[] = [
  { value: "approved", label: "Approve" },
  { value: "approved_with_comments", label: "Approve with comments" },
  { value: "rework_required", label: "Request rework" },
  { value: "rejected", label: "Reject" },
];

export default function ProjectWorkspacePage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [artefactVersions, setArtefactVersions] = useState<ArtefactVersion[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [taskRequest, setTaskRequest] = useState("");
  const [startingRun, setStartingRun] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [reviewerId, setReviewerId] = useState("");
  const [decision, setDecision] = useState<ReviewDecision>("approved");
  const [comments, setComments] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    // Run/artefact state is intentionally kept in memory only for this
    // session — there's no "list runs for a project" endpoint yet, so a
    // page refresh loses track of an in-flight run. See implementation
    // ledger.
    //
    // The guard below prevents setState after this component unmounts (or
    // projectId changes again) before the fetch resolves. See
    // https://react.dev/learn/synchronizing-with-effects#fetching-data.
    let ignore = false;
    (async () => {
      try {
        const data = await api.getProject(projectId);
        if (!ignore) {
          setProject(data);
          setLoadError(null);
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
      setProject(updatedProject);
      setRun(await api.getRun(run.id));
      setArtefactVersions(await api.getRunArtefactVersions(run.id)); // may have just been promoted to baseline
      setComments("");
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

  const canStartRun = project.status !== "completed" && (!run || run.state === "completed");
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
              <div className="field">
                <label htmlFor="reviewer-id">Reviewer</label>
                <input
                  id="reviewer-id"
                  value={reviewerId}
                  onChange={(e) => setReviewerId(e.target.value)}
                  placeholder="reviewer@example.test"
                  disabled={submittingReview}
                />
              </div>
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
    </main>
  );
}
