// Mirrors backend/app/api/schemas.py exactly. Keep in sync by hand for now —
// there's no shared schema generation yet (see implementation ledger).

export type ReviewDecision = "approved" | "approved_with_comments" | "rework_required" | "rejected";

export interface Project {
  id: string;
  name: string;
  current_phase: string;
  phase_status: string;
  status: string;
  created_at: string;
}

export interface Run {
  id: string;
  project_id: string;
  agent_id: string;
  phase: string;
  run_number: number;
  state: string;
}

export interface ArtefactVersion {
  id: string;
  artefact_id: string;
  artefact_type: string;
  version_label: string;
  file_path: string;
  checksum: string;
  status: string;
  created_at: string;
}

export interface AgentSummary {
  id: string;
  display_name: string;
  kind: string;
  phase: string | null;
  version: string;
}
