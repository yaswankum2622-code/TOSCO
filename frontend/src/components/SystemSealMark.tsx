interface SystemSealMarkProps {
  label?: string;
  testId?: string;
  tone?: "sealed" | "armed" | "broken";
}

function SystemSealMark({ label = "SEALED", testId, tone = "sealed" }: SystemSealMarkProps) {
  return (
    <span
      className={`system-seal-mark system-seal-mark--${tone}`}
      data-testid={testId}
      aria-label={label}
    >
      <svg className="system-seal-mark__ring" viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.35" />
        <circle cx="24" cy="24" r="14" stroke="currentColor" strokeWidth="1" strokeOpacity="0.55" />
        <circle cx="24" cy="24" r="8" stroke="currentColor" strokeWidth="1" strokeOpacity="0.75" />
        {Array.from({ length: 6 }, (_, index) => (
          <ellipse
            key={`seal-mark-${index}`}
            cx="24"
            cy="24"
            rx="18"
            ry="8"
            transform={`rotate(${index * 30} 24 24)`}
            stroke="currentColor"
            strokeWidth="0.75"
            strokeOpacity="0.28"
          />
        ))}
      </svg>
      <span className="system-seal-mark__label">{label}</span>
    </span>
  );
}

export default SystemSealMark;
