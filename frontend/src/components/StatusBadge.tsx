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
