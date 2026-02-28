import { useEffect, useMemo, useState, type DragEvent } from "react";

import { MetricCard } from "./components/MetricCard";
import { ResultRow } from "./components/ResultRow";
import { SegmentedControl } from "./components/SegmentedControl";
import { StatusBadge } from "./components/StatusBadge";
import { ThresholdControl } from "./components/ThresholdControl";
import { UploadDropzone } from "./components/UploadDropzone";
import {
  fetchBackendHealth,
  fetchHistoryStatus,
  processTenderWorkbook,
} from "./lib/api";
import type { HistoryStatus, ProcessOptions, TenderSession } from "./lib/types";

type LoadState = "idle" | "loading" | "ready" | "error";

const defaultProcessOptions: ProcessOptions = {
  outputFormat: "json",
  similarityThreshold: 0.72,
};

const outputFormatOptions: Array<{
  description: string;
  label: string;
  value: ProcessOptions["outputFormat"];
}> = [
  { label: "JSON", value: "json", description: "Structured export" },
  { label: "Excel", value: "excel", description: "Spreadsheet handoff" },
];

const formatTimestamp = (value: string) =>
  new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));

function healthTone(status: string) {
  // "checking" is an in-flight state, not a failure. Keeping that distinct
  // avoids flashing a red badge before the real backend result arrives.
  if (status === "checking") {
    return "neutral" as const;
  }

  if (status === "ok") {
    return "success" as const;
  }

  return "danger" as const;
}

function App() {
  // The dashboard keeps network state local because the interaction surface is
  // small and the take-home brief explicitly does not need a state library.
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [session, setSession] = useState<TenderSession | null>(null);
  const [expandedResultId, setExpandedResultId] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState("checking");
  const [historyStatus, setHistoryStatus] = useState<HistoryStatus | null>(null);
  const [pageState, setPageState] = useState<LoadState>("loading");
  const [processState, setProcessState] = useState<LoadState>("idle");
  const [isDragActive, setIsDragActive] = useState(false);
  const [screenMessage, setScreenMessage] = useState(
    "Waiting for a tender workbook.",
  );
  const [options, setOptions] = useState<ProcessOptions>(defaultProcessOptions);

  useEffect(() => {
    let active = true;

    async function loadDashboardChrome() {
      try {
        const [health, history] = await Promise.all([
          fetchBackendHealth(),
          fetchHistoryStatus(),
        ]);

        if (!active) {
          return;
        }

        setHealthStatus(health.status);
        setHistoryStatus(history);
        setPageState("ready");
      } catch (error) {
        if (!active) {
          return;
        }

        setHealthStatus("offline");
        setPageState("error");
        setScreenMessage(
          error instanceof Error
            ? error.message
            : "Unable to initialize the dashboard.",
        );
      }
    }

    void loadDashboardChrome();

    return () => {
      active = false;
    };
  }, []);

  const progressSnapshot = useMemo(() => {
    if (!session) {
      return {
        total: 0,
        completed: 0,
        failed: 0,
        label: processState === "loading" ? "processing" : "idle",
      };
    }

    const failed = session.results.filter((item) => item.status === "failed").length;
    const completed = session.results.filter((item) => item.status !== "failed").length;

    return {
      total: session.summary.totalQuestions,
      completed,
      failed,
      label: session.summary.overallStatus,
    };
  }, [processState, session]);

  const summarySnapshot = useMemo(
    () => ({
      highRiskCount: session?.summary.highRiskCount ?? 0,
      inconsistentCount: session?.summary.inconsistentCount ?? 0,
      overallStatus: session?.summary.overallStatus ?? "awaiting run",
    }),
    [session],
  );

  function applySelectedFile(file: File | null) {
    setSelectedFile(file);
    setIsDragActive(false);

    // Routing every file-selection path through one helper keeps drag-and-drop
    // and manual browse interactions perfectly aligned.
    if (file) {
      setScreenMessage(`${file.name} staged and ready for processing.`);
      return;
    }

    setScreenMessage("Waiting for a tender workbook.");
  }

  function updateOutputFormat(value: ProcessOptions["outputFormat"]) {
    setOptions((current) => ({
      ...current,
      outputFormat: value,
    }));
  }

  function updateSimilarityThreshold(value: number) {
    const normalizedValue = Math.min(0.99, Math.max(0.1, Number(value.toFixed(2))));

    setOptions((current) => ({
      ...current,
      similarityThreshold: normalizedValue,
    }));
  }

  function handleDragEnter(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragActive(true);
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();

    // Drag leave fires while moving across child nodes; only clear the visual
    // state when the pointer has truly exited the drop surface.
    if (
      event.relatedTarget instanceof Node &&
      event.currentTarget.contains(event.relatedTarget)
    ) {
      return;
    }

    setIsDragActive(false);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();

    const transferredFiles = event.dataTransfer.files;
    const nextFile =
      typeof transferredFiles?.item === "function"
        ? transferredFiles.item(0)
        : transferredFiles?.[0] ?? null;

    applySelectedFile(nextFile);
  }

  async function handleProcessClick() {
    if (!selectedFile) {
      setScreenMessage("Select a tender workbook before starting the run.");
      return;
    }

    setProcessState("loading");
    setScreenMessage(`Processing ${selectedFile.name}...`);

    try {
      const nextSession = await processTenderWorkbook(selectedFile, options);

      setSession(nextSession);
      setExpandedResultId(null);
      setProcessState("ready");
      setScreenMessage(
        `${nextSession.summary.totalQuestions} questions analyzed for ${selectedFile.name}.`,
      );
    } catch (error) {
      setProcessState("error");
      setScreenMessage(
        error instanceof Error ? error.message : "Processing failed unexpectedly.",
      );
    }
  }

  function handleDownload(kind: "json" | "excel") {
    if (!session) {
      setScreenMessage("Run a processing session before downloading outputs.");
      return;
    }

    // The download payload is intentionally simple; the goal is to demonstrate
    // the output affordance expected by the brief, not a real export pipeline.
    const payload =
      kind === "json"
        ? JSON.stringify(session, null, 2)
        : [
            "Question,Domain,Alignment,Confidence,Risk,Status",
            ...session.results.map((result) =>
              [
                result.question,
                result.domain,
                result.alignment,
                result.confidence,
                result.risk,
                result.status,
              ].join(","),
            ),
          ].join("\n");

    const mimeType =
      kind === "json"
        ? "application/json"
        : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

    const extension = kind === "json" ? "json" : "csv";
    const blob = new Blob([payload], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = `${session.sessionId}.${extension}`;
    anchor.click();
    window.URL.revokeObjectURL(url);

    setScreenMessage(`Prepared ${kind.toUpperCase()} download for ${session.fileName}.`);
  }

  return (
    <div className="app-shell">
      <div className="app-shell__mesh" aria-hidden="true" />

      <main className="dashboard">
        <header className="app-header">
          <div className="app-header__brand">
            <p className="app-header__eyebrow">Tender audit console</p>
            <h1>Tender Response Automation</h1>
          </div>

          <div className="app-header__status">
            <StatusBadge
              label={`Backend health: ${healthStatus}`}
              tone={healthTone(healthStatus)}
            />
            <StatusBadge
              label={summarySnapshot.overallStatus}
              tone={processState === "error" ? "danger" : "warning"}
            />
          </div>
        </header>

        <section className="control-strip">
          <article className="panel panel--upload">
            <div className="panel__header">
              <div>
                <p className="panel__eyebrow">Input</p>
                <h2>Upload tender workbook</h2>
              </div>
              <StatusBadge
                label={selectedFile ? "file ready" : "awaiting file"}
                tone={selectedFile ? "success" : "neutral"}
              />
            </div>

            <UploadDropzone
              fileName={selectedFile?.name ?? null}
              inputId="tender-upload"
              isDragActive={isDragActive}
              label="Upload tender workbook"
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onFileChange={applySelectedFile}
            />

            <div className="field-grid field-grid--custom">
              <SegmentedControl
                label="Output format"
                options={outputFormatOptions}
                value={options.outputFormat}
                onChange={updateOutputFormat}
              />
              <ThresholdControl
                label="Similarity threshold"
                max={0.99}
                min={0.1}
                step={0.01}
                value={options.similarityThreshold}
                onChange={updateSimilarityThreshold}
              />
            </div>

            <button
              className="primary-button"
              disabled={processState === "loading"}
              type="button"
              onClick={() => void handleProcessClick()}
            >
              {processState === "loading" ? "Processing..." : "Process Tender"}
            </button>
          </article>
        </section>

        <section className="spotlight" aria-labelledby="processing-spotlight-title">
          <div className="spotlight__header">
            <div>
              <p className="panel__eyebrow">Priority review</p>
              <h2 id="processing-spotlight-title">Processing spotlight</h2>
            </div>
            <StatusBadge
              label={summarySnapshot.overallStatus}
              tone={processState === "error" ? "danger" : "warning"}
            />
          </div>

          <div className="spotlight-grid">
            <article className="spotlight-card spotlight-card--primary">
              <p className="spotlight-card__kicker">Current batch state</p>
              <p className="spotlight-card__value">{progressSnapshot.label}</p>
              <p className="spotlight-card__detail">{screenMessage}</p>

              <div className="spotlight-card__chips">
                <StatusBadge
                  label={`Backend health: ${healthStatus}`}
                  tone={healthTone(healthStatus)}
                />
                <StatusBadge
                  label={
                    selectedFile ? `Queued: ${selectedFile.name}` : "No file staged"
                  }
                  tone={selectedFile ? "success" : "neutral"}
                />
              </div>
            </article>

            <MetricCard
              className="metric-card--spotlight"
              eyebrow="Total questions"
              value={String(progressSnapshot.total)}
              detail="Workbook rows evaluated in the current session."
            />
            <MetricCard
              className="metric-card--spotlight"
              eyebrow="Completed"
              value={String(progressSnapshot.completed)}
              detail="Rows with a usable answer or warning."
            />
            <MetricCard
              className="metric-card--spotlight"
              eyebrow="High-risk items"
              value={String(summarySnapshot.highRiskCount)}
              detail="Rows that require careful human sign-off."
            />
            <MetricCard
              className="metric-card--spotlight"
              eyebrow="Failed"
              value={String(progressSnapshot.failed)}
              detail="Rows isolated without blocking the rest of the run."
            />
          </div>
        </section>

        <section className="results-layout">
          <article className="panel panel--results">
            <div className="panel__header">
              <div>
                <p className="panel__eyebrow">Audit trail</p>
                <h2>Question Results</h2>
              </div>
              {session ? (
                <StatusBadge
                  label={`${session.summary.totalQuestions} questions analyzed`}
                  tone="success"
                />
              ) : null}
            </div>

            {session ? (
              <div className="results-table-wrap">
                <table className="results-table">
                  <thead>
                    <tr>
                      <th>Question</th>
                      <th>Domain</th>
                      <th>Alignment</th>
                      <th>Confidence</th>
                      <th>Risk</th>
                      <th>Status</th>
                      <th>Inspect</th>
                    </tr>
                  </thead>
                  <tbody>
                    {session.results.map((result) => (
                      <ResultRow
                        key={result.id}
                        isExpanded={expandedResultId === result.id}
                        result={result}
                        onToggle={(id) =>
                          setExpandedResultId((current) =>
                            current === id ? null : id,
                          )
                        }
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-state">
                Process a workbook to populate the results table and retrieval
                evidence panels.
              </p>
            )}
          </article>

          <aside className="results-sidebar">
            <article className="panel panel--summary">
              <div className="panel__header">
                <div>
                  <p className="panel__eyebrow">Executive view</p>
                  <h2>Summary</h2>
                </div>
                {session ? (
                  <StatusBadge
                    label={session.summary.overallStatus}
                    tone="warning"
                  />
                ) : null}
              </div>

              {session ? (
                <>
                  <div className="metric-cluster metric-cluster--summary">
                    <MetricCard
                      eyebrow="Questions analyzed"
                      value={`${session.summary.totalQuestions} questions analyzed`}
                      detail="Total workload included in the current run."
                    />
                    <MetricCard
                      eyebrow="High-risk items"
                      value={String(session.summary.highRiskCount)}
                      detail="Rows that need close human review before submission."
                    />
                    <MetricCard
                      eyebrow="Inconsistent items"
                      value={String(session.summary.inconsistentCount)}
                      detail="Rows where historical evidence conflicts."
                    />
                  </div>

                  <div className="summary-list">
                    <p>Success count: {session.summary.successCount}</p>
                    <p>Failed count: {session.summary.failedCount}</p>
                    <p>Overall status: {session.summary.overallStatus}</p>
                  </div>
                </>
              ) : (
                <p className="empty-state">
                  Summary metrics will appear after the first processing run.
                </p>
              )}
            </article>

            <article className="panel panel--history">
              <div className="panel__header">
                <div>
                  <p className="panel__eyebrow">Knowledge base</p>
                  <h2>History status</h2>
                </div>
                <StatusBadge
                  label={pageState === "error" ? "attention" : "available"}
                  tone={pageState === "error" ? "danger" : "success"}
                />
              </div>

              {historyStatus ? (
                <>
                  <div className="history-metrics">
                    <MetricCard
                      eyebrow="Indexed entries"
                      value={String(historyStatus.itemCount)}
                      detail="Historical tender answers ready for retrieval."
                    />
                    <MetricCard
                      eyebrow="Last sync"
                      value={formatTimestamp(historyStatus.lastUpdated)}
                      detail="Most recent memory refresh currently visible."
                    />
                  </div>

                  <ul className="distribution-list">
                    {historyStatus.domainDistribution.map((entry) => (
                      <li key={entry.domain}>
                        <span>{entry.domain}</span>
                        <strong>{entry.count}</strong>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="empty-state">Loading history telemetry...</p>
              )}
            </article>

            <article className="panel">
              <div className="panel__header">
                <div>
                  <p className="panel__eyebrow">Exports</p>
                  <h2>Download package</h2>
                </div>
              </div>

              <div className="download-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => handleDownload("json")}
                >
                  Download JSON
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => handleDownload("excel")}
                >
                  Download Excel
                </button>
              </div>
            </article>
          </aside>
        </section>
      </main>
    </div>
  );
}

export default App;
