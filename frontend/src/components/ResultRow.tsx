import { StatusBadge, alignmentTone, resultTone, riskTone } from "./StatusBadge";
import type { TenderQuestionResult } from "../lib/types";

type ResultRowProps = {
  isExpanded: boolean;
  onToggle: (id: string) => void;
  result: TenderQuestionResult;
};

const percent = (value: number) => `${Math.round(value * 100)}%`;

export function ResultRow({ isExpanded, onToggle, result }: ResultRowProps) {
  return (
    <>
      <tr className="result-row">
        <td>{result.question}</td>
        <td>{result.domain}</td>
        <td>
          <StatusBadge
            label={result.alignment}
            tone={alignmentTone(result.alignment)}
          />
        </td>
        <td>{percent(result.confidence)}</td>
        <td>
          <StatusBadge label={result.risk} tone={riskTone(result.risk)} />
        </td>
        <td>
          <StatusBadge label={result.status} tone={resultTone(result.status)} />
        </td>
        <td>
          <button
            aria-expanded={isExpanded}
            aria-label={`Expand result for ${result.question}`}
            className="row-action"
            type="button"
            onClick={() => onToggle(result.id)}
          >
            {isExpanded ? "Hide details" : "View details"}
          </button>
        </td>
      </tr>

      {isExpanded ? (
        <tr className="result-row__details">
          <td colSpan={7}>
            <div className="detail-grid">
              <section className="detail-panel">
                <h4>Original question</h4>
                <p>{result.question}</p>
              </section>

              <section className="detail-panel">
                <h4>Generated answer</h4>
                <p>
                  {result.generatedAnswer || "No answer generated for this question."}
                </p>
              </section>

              <section className="detail-panel">
                <h4>Historical matches</h4>
                <ul className="detail-list">
                  {result.historicalMatches.map((match) => (
                    <li key={`${result.id}-${match.source}`}>
                      <strong>{match.title}</strong>
                      <span>{match.source}</span>
                      <span>{percent(match.similarity)}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="detail-panel">
                <h4>Risk flags</h4>
                {result.riskFlags.length > 0 ? (
                  <ul className="detail-list">
                    {result.riskFlags.map((flag) => (
                      <li key={`${result.id}-${flag}`}>{flag}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No material risk flags detected.</p>
                )}

                {result.errorMessage ? (
                  <>
                    <h4>Error message</h4>
                    <p>{result.errorMessage}</p>
                  </>
                ) : null}
              </section>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}
