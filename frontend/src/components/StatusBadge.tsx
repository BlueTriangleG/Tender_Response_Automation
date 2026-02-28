import type { AlignmentStatus, ResultStatus, RiskLevel } from "../lib/types";

type BadgeTone = "neutral" | "success" | "warning" | "danger";

type StatusBadgeProps = {
  label: string;
  tone?: BadgeTone;
};

const toneClassMap: Record<BadgeTone, string> = {
  neutral: "status-badge",
  success: "status-badge status-badge--success",
  warning: "status-badge status-badge--warning",
  danger: "status-badge status-badge--danger",
};

export function StatusBadge({ label, tone = "neutral" }: StatusBadgeProps) {
  return <span className={toneClassMap[tone]}>{label}</span>;
}

export function riskTone(level: RiskLevel): BadgeTone {
  if (level === "high") {
    return "danger";
  }

  if (level === "medium") {
    return "warning";
  }

  return "success";
}

export function alignmentTone(status: AlignmentStatus): BadgeTone {
  if (status === "aligned") {
    return "success";
  }

  if (status === "inconsistent") {
    return "danger";
  }

  return "warning";
}

export function resultTone(status: ResultStatus): BadgeTone {
  if (status === "success") {
    return "success";
  }

  if (status === "failed") {
    return "danger";
  }

  return "warning";
}
