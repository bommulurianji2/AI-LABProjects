import type { AgentSummary, ArtefactVersion, Project, ReviewDecision, Run } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new ApiError(res.status, detail || res.statusText);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const api = {
  listAgents: () => request<AgentSummary[]>("/agents"),

  listProjects: () => request<Project[]>("/projects"),

  createProject: (name: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) }),

  getProject: (projectId: string) => request<Project>(`/projects/${projectId}`),

  startRun: (projectId: string, taskRequest: string) =>
    request<Run>(`/projects/${projectId}/runs`, {
      method: "POST",
      body: JSON.stringify({ task_request: taskRequest }),
    }),

  getRun: (runId: string) => request<Run>(`/runs/${runId}`),

  // A run can produce more than one artefact (e.g. the UX Design Agent's
  // spec + prototype) — this always returns every version it produced,
  // possibly an empty array if none have been generated yet.
  getRunArtefactVersions: (runId: string) => request<ArtefactVersion[]>(`/runs/${runId}/artefact-versions`),

  downloadUrlForVersion: (versionId: string) => `${API_BASE_URL}/artefact-versions/${versionId}/download`,

  submitReview: (runId: string, reviewerId: string, decision: ReviewDecision, comments: string[]) =>
    request<Project>(`/runs/${runId}/review`, {
      method: "POST",
      body: JSON.stringify({ reviewer_id: reviewerId, decision, comments }),
    }),
};
