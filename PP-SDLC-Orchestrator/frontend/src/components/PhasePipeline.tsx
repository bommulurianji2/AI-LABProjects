import { Fragment } from "react";
import { formatLabel } from "@/lib/format";

// Mirrors backend/app/domain/enums.py::LIFECYCLE_PHASES exactly — kept in
// sync by hand for now, same convention already used for the rest of the
// API shape in lib/types.ts.
const LIFECYCLE_PHASES = [
  "analysis",
  "ux_design",
  "technical_design",
  "data_integration",
  "governance_security",
  "build",
  "validation_qa",
  "test",
  "deploy",
  "hypercare_closure",
];

interface PhasePipelineProps {
  currentPhase: string;
  phaseStatus: string;
  projectStatus: string;
}

export default function PhasePipeline({ currentPhase, phaseStatus, projectStatus }: PhasePipelineProps) {
  const currentIndex = LIFECYCLE_PHASES.indexOf(currentPhase);
  const projectCompleted = projectStatus === "completed";

  return (
    <div className="pipeline" aria-label="Project lifecycle progress">
      {LIFECYCLE_PHASES.map((phase, index) => {
        const isDone = projectCompleted || index < currentIndex;
        const isCurrent = !projectCompleted && index === currentIndex;

        let dotClass = "pipeline-dot";
        let content: React.ReactNode = index + 1;
        if (isDone) {
          dotClass += " done";
          content = "✓";
        } else if (isCurrent) {
          dotClass += " current";
          if (phaseStatus === "rework") dotClass += " warning";
        }

        return (
          <Fragment key={phase}>
            {index > 0 && <div className={`pipeline-connector${isDone || isCurrent ? " done" : ""}`} />}
            <div className={`pipeline-step${isCurrent ? " current" : ""}`}>
              <div className={dotClass} title={formatLabel(phase)}>
                {content}
              </div>
              <div className="pipeline-label">
                {formatLabel(phase)}
                {isCurrent && <div className="muted">{formatLabel(phaseStatus)}</div>}
              </div>
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}
