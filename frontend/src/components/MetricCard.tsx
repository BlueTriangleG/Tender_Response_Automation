type MetricCardProps = {
  className?: string;
  eyebrow: string;
  value: string;
  detail: string;
};

export function MetricCard({
  className,
  eyebrow,
  value,
  detail,
}: MetricCardProps) {
  return (
    <article className={className ? `metric-card ${className}` : "metric-card"}>
      <p className="metric-card__eyebrow">{eyebrow}</p>
      <p className="metric-card__value">{value}</p>
      <p className="metric-card__detail">{detail}</p>
    </article>
  );
}
