type ThresholdControlProps = {
  label: string;
  max: number;
  min: number;
  onChange: (value: number) => void;
  step: number;
  value: number;
};

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

export function ThresholdControl({
  label,
  max,
  min,
  onChange,
  step,
  value,
}: ThresholdControlProps) {
  const progress = ((value - min) / (max - min)) * 100;

  return (
    <div aria-label={label} className="custom-field">
      <div className="custom-field__header">
        <span className="custom-field__label">{label}</span>
        <strong className="threshold-control__value">{value.toFixed(2)}</strong>
      </div>

      <div className="threshold-control">
        <button
          aria-label={`Decrease ${label}`}
          className="threshold-control__stepper"
          type="button"
          onClick={() => onChange(clamp(value - step, min, max))}
        >
          -
        </button>

        <div className="threshold-control__track" aria-hidden="true">
          <div
            className="threshold-control__fill"
            style={{ width: `${progress}%` }}
          />
        </div>

        <button
          aria-label={`Increase ${label}`}
          className="threshold-control__stepper"
          type="button"
          onClick={() => onChange(clamp(value + step, min, max))}
        >
          +
        </button>
      </div>

      <input
        aria-label={label}
        className="sr-only"
        max={max}
        min={min}
        step={step}
        type="range"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <p className="custom-field__hint">
        Tighten for stricter retrieval matches, loosen for broader reuse.
      </p>
    </div>
  );
}
