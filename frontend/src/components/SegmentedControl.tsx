type SegmentedOption<T extends string> = {
  description?: string;
  label: string;
  value: T;
};

type SegmentedControlProps<T extends string> = {
  label: string;
  onChange: (value: T) => void;
  options: SegmentedOption<T>[];
  value: T;
};

export function SegmentedControl<T extends string>({
  label,
  onChange,
  options,
  value,
}: SegmentedControlProps<T>) {
  return (
    <div aria-label={label} className="custom-field">
      <span className="custom-field__label">{label}</span>
      <div className="segmented-control" role="group" aria-label={label}>
        {options.map((option) => {
          const isActive = option.value === value;

          return (
            <button
              key={option.value}
              aria-pressed={isActive}
              className={
                isActive
                  ? "segmented-control__button segmented-control__button--active"
                  : "segmented-control__button"
              }
              type="button"
              onClick={() => onChange(option.value)}
            >
              <span>{option.label}</span>
              {option.description ? (
                <small>{option.description}</small>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
