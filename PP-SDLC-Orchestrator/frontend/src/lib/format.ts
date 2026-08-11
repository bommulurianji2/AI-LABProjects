// Backend enums are lower_snake_case (e.g. "waiting_for_human_review").
// This turns them into readable labels for display only — never use the
// output of this function as a value sent back to the API.
const ACRONYMS = new Set(["ux", "qa", "iq"]);

export function formatLabel(value: string): string {
  return value
    .split("_")
    .map((word) =>
      ACRONYMS.has(word.toLowerCase())
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

export type StatusVariant = "success" | "warning" | "danger" | "info" | "accent" | "neutral";

// Maps every RunState / ReviewDecision / PhaseStatus / project status value
// this app displays to one semantic color bucket, so the same word always
// reads the same way everywhere (a run's badge, its history row, the phase
// pipeline dot) instead of every call site inventing its own mapping.
const STATUS_VARIANTS: Record<string, StatusVariant> = {
  completed: "success",
  approved: "success",
  approved_with_comments: "success",
  baseline: "success",

  waiting_for_human_review: "info",
  in_review: "info",
  running: "info",
  queued: "info",
  ready_for_review: "info",
  awaiting_review: "info",
  draft: "info",

  rework_required: "warning",
  rework: "warning",
  pending: "neutral",
  not_started: "neutral",
  ready: "neutral",
  active: "accent",

  rejected: "danger",
  failed: "danger",
  cancelled: "danger",
  blocked: "danger",
};

export function statusVariant(value: string): StatusVariant {
  return STATUS_VARIANTS[value] ?? "neutral";
}

export function badgeClass(value: string): string {
  return `badge badge-${statusVariant(value)}`;
}
