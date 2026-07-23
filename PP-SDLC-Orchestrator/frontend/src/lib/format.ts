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
