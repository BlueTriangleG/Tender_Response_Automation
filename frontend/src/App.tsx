import { Fragment, useEffect, useMemo, useState, type DragEvent } from "react";

import { BatchUploadDropzone } from "./components/BatchUploadDropzone";
import { MetricCard } from "./components/MetricCard";
import { StatusBadge } from "./components/StatusBadge";
import { ThresholdControl } from "./components/ThresholdControl";
import { UploadDropzone } from "./components/UploadDropzone";
import {
  fetchBackendHealth,
  fetchHistoryStatus,
  ingestHistoryFiles,
  processTenderWorkbook,
} from "./lib/api";
import type {
  HistoryIngestResponse,
  HistoryStatus,
  HistoryIngestOptions,
  TenderAutofillQuestion,
  TenderAutofillResponse,
} from "./lib/types";

type LoadState = "idle" | "loading" | "ready" | "error";

const defaultKnowledgeBaseOptions: HistoryIngestOptions = {
  outputFormat: "json",
  similarityThreshold: 0.72,
};
const defaultAlignmentThreshold = 0.82;

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

function mergeKnowledgeBaseFiles(currentFiles: File[], incomingFiles: File[]) {
  const fileMap = new Map<string, File>();

  for (const file of [...currentFiles, ...incomingFiles]) {
    const fileKey = [file.name, file.size, file.lastModified, file.type].join(":");
    fileMap.set(fileKey, file);
  }

  return Array.from(fileMap.values());
}

function batchHasFailures(response: HistoryIngestResponse) {
  return response.failedFileCount > 0 || response.files.some((file) => file.failedRowCount > 0);
}

function confidenceTone(level: TenderAutofillQuestion["confidenceLevel"]) {
  if (level === "high") {
    return "success" as const;
  }

  if (level === "medium") {
    return "warning" as const;
  }

  return "danger" as const;
}

function questionStatusTone(question: TenderAutofillQuestion) {
  if (question.status === "completed") {
    return "success" as const;
  }

  if (question.errorMessage) {
    return "danger" as const;
  }

  return "warning" as const;
}

function isCsvFile(file: File) {
  return file.name.toLowerCase().endsWith(".csv");
}

function App() {
  // The dashboard keeps network state local because the interaction surface is
  // small and the take-home brief explicitly does not need a state library.
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [session, setSession] = useState<TenderAutofillResponse | null>(null);
  const [expandedResultId, setExpandedResultId] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState("checking");
  const [historyStatus, setHistoryStatus] = useState<HistoryStatus | null>(null);
  const [pageState, setPageState] = useState<LoadState>("loading");
  const [processState, setProcessState] = useState<LoadState>("idle");
  const [knowledgeBaseState, setKnowledgeBaseState] = useState<LoadState>("idle");
  const [isDragActive, setIsDragActive] = useState(false);
  const [screenMessage, setScreenMessage] = useState(
    "Waiting for a tender csv.",
  );
  const [knowledgeBaseFiles, setKnowledgeBaseFiles] = useState<File[]>([]);
  const [knowledgeBaseMessage, setKnowledgeBaseMessage] = useState(
    "Upload history files to build the knowledge base.",
  );
  const [knowledgeBaseRun, setKnowledgeBaseRun] =
    useState<HistoryIngestResponse | null>(null);
  const [alignmentThreshold, setAlignmentThreshold] = useState(
    defaultAlignmentThreshold,
  );

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

    return {
      total: session.summary.totalQuestionsProcessed,
      completed: session.summary.completedQuestions,
      failed: session.summary.failedQuestions,
      label: session.summary.overallCompletionStatus,
    };
  }, [processState, session]);

  const summarySnapshot = useMemo(
    () => ({
      flaggedCount:
        session?.summary.flaggedHighRiskOrInconsistentResponses ?? 0,
      overallStatus: session?.summary.overallCompletionStatus ?? "awaiting run",
    }),
    [session],
  );
  const knowledgeBaseFileNames = useMemo(
    () => knowledgeBaseFiles.map((file) => file.name),
    [knowledgeBaseFiles],
  );
  const hasKnowledgeBaseFiles = knowledgeBaseFileNames.length > 0;

  function applySelectedFile(file: File | null) {
    setIsDragActive(false);

    if (file && !isCsvFile(file)) {
      setSelectedFile(null);
      setScreenMessage("Autofill only accepts .csv files.");
      return;
    }

    setSelectedFile(file);

    // Routing every file-selection path through one helper keeps drag-and-drop
    // and manual browse interactions perfectly aligned.
    if (file) {
      setScreenMessage(`${file.name} staged and ready for processing.`);
      return;
    }

    setScreenMessage("Waiting for a tender csv.");
  }

  function updateAlignmentThreshold(value: number) {
    const normalizedValue = Math.min(0.99, Math.max(0.1, Number(value.toFixed(2))));
    setAlignmentThreshold(normalizedValue);
  }

  function applyKnowledgeBaseFiles(files: File[]) {
    if (files.length === 0) {
      setKnowledgeBaseFiles([]);
      setKnowledgeBaseMessage("Upload history files to build the knowledge base.");
      return;
    }

    setKnowledgeBaseFiles((currentFiles) => {
      const mergedFiles = mergeKnowledgeBaseFiles(currentFiles, files);
      setKnowledgeBaseMessage(
        `${mergedFiles.length} files staged for knowledge base ingest.`,
      );
      return mergedFiles;
    });
  }

  function removeKnowledgeBaseFile(fileName: string) {
    setKnowledgeBaseFiles((currentFiles) => {
      const nextFiles = currentFiles.filter((file) => file.name !== fileName);

      if (nextFiles.length === 0) {
        setKnowledgeBaseMessage("Upload history files to build the knowledge base.");
      } else {
        setKnowledgeBaseMessage(
          `${nextFiles.length} files staged for knowledge base ingest.`,
        );
      }

      return nextFiles;
    });
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
      setScreenMessage("Select a tender csv before starting the run.");
      return;
    }

    setProcessState("loading");
    setScreenMessage(`Autofilling ${selectedFile.name}...`);

    try {
      const nextSession = await processTenderWorkbook(selectedFile, {
        alignmentThreshold,
      });

      setSession(nextSession);
      setExpandedResultId(null);
      setProcessState("ready");
      setScreenMessage(
        `${nextSession.summary.totalQuestionsProcessed} questions analyzed for ${selectedFile.name}.`,
      );
    } catch (error) {
      setProcessState("error");
      setScreenMessage(
        error instanceof Error ? error.message : "Processing failed unexpectedly.",
      );
    }
  }

  async function handleKnowledgeBaseIngest() {
    if (knowledgeBaseFiles.length === 0) {
      setKnowledgeBaseMessage("Select one or more history files before starting ingest.");
      return;
    }

    setKnowledgeBaseState("loading");
    setKnowledgeBaseMessage(
      `Syncing ${knowledgeBaseFiles.length} files to the knowledge base...`,
    );

    try {
      const response = await ingestHistoryFiles(
        knowledgeBaseFiles,
        defaultKnowledgeBaseOptions,
      );
      const hasFailures = batchHasFailures(response);

      setKnowledgeBaseRun(response);
      setKnowledgeBaseState("ready");
      setKnowledgeBaseMessage(
        `Knowledge base sync complete: ${response.processedFileCount} processed, ${response.failedFileCount} failed.`,
      );
      if (!hasFailures) {
        setKnowledgeBaseFiles([]);
      }
      setHistoryStatus((current) => ({
        itemCount: (current?.itemCount ?? 0) + response.processedFileCount,
        lastUpdated: new Date().toISOString(),
        domainDistribution: current?.domainDistribution ?? [],
      }));
    } catch (error) {
      setKnowledgeBaseState("error");
      setKnowledgeBaseMessage(
        error instanceof Error ? error.message : "Knowledge base ingest failed unexpectedly.",
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
            "Question,Answer,Domain,Confidence,Aligned,Status",
            ...session.questions.map((result) =>
              [
                JSON.stringify(result.originalQuestion),
                JSON.stringify(result.generatedAnswer),
                result.domainTag,
                result.confidenceLevel,
                String(result.historicalAlignmentIndicator),
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

    setScreenMessage(
      `Prepared ${kind.toUpperCase()} download for ${session.sourceFileName}.`,
    );
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

        <section
          aria-labelledby="knowledge-base-builder-title"
          className="knowledge-base-strip"
        >
          <article className="panel panel--knowledge-base">
            <div className="panel__header">
              <div>
                <p className="panel__eyebrow">Knowledge base</p>
                <h2 id="knowledge-base-builder-title">Build knowledge base</h2>
              </div>
              <StatusBadge
                label={
                  knowledgeBaseState === "loading"
                    ? "syncing"
                    : hasKnowledgeBaseFiles
                      ? "files queued"
                      : "awaiting files"
                }
                tone={
                  knowledgeBaseState === "error"
                    ? "danger"
                    : hasKnowledgeBaseFiles
                      ? "success"
                      : "neutral"
                }
              />
            </div>

            <div className="knowledge-base-layout">
              <div className="knowledge-base-layout__primary">
                <BatchUploadDropzone
                  inputId="knowledge-base-upload"
                  label="Upload knowledge base files"
                  onFilesChange={applyKnowledgeBaseFiles}
                />

                <button
                  className="primary-button"
                  disabled={knowledgeBaseState === "loading"}
                  type="button"
                  onClick={() => void handleKnowledgeBaseIngest()}
                >
                  {knowledgeBaseState === "loading"
                    ? "Syncing..."
                    : "Ingest Knowledge Files"}
                </button>
              </div>

              <div className="knowledge-base-layout__secondary">
                <div className="sync-summary">
                  <p className="sync-summary__message">{knowledgeBaseMessage}</p>

                  <div className="knowledge-queue">
                    <h3>Files queued for sync</h3>
                    {hasKnowledgeBaseFiles ? (
                      <ul className="detail-list detail-list--stacked">
                        {knowledgeBaseFileNames.map((fileName) => (
                          <li key={fileName}>
                            <span>{fileName}</span>
                            <div className="queue-actions">
                              <strong>queued</strong>
                              <button
                                className="secondary-button queue-action"
                                type="button"
                                onClick={() => removeKnowledgeBaseFile(fileName)}
                              >
                                Remove {fileName} from queue
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="empty-state">
                        Select multiple files to preview the batch before sending it.
                      </p>
                    )}
                  </div>

                  {knowledgeBaseRun ? (
                    <div className="knowledge-results">
                      <h3>Latest ingest result</h3>
                      <ul className="detail-list detail-list--stacked">
                        <li>
                          <span>Batch request</span>
                          <strong>{knowledgeBaseRun.requestId}</strong>
                        </li>
                        <li>
                          <span>Processed</span>
                          <strong>{knowledgeBaseRun.processedFileCount}</strong>
                        </li>
                        <li>
                          <span>Failed</span>
                          <strong>{knowledgeBaseRun.failedFileCount}</strong>
                        </li>
                        {knowledgeBaseRun.files.map((fileResult, index) => (
                          <li
                            key={`${fileResult.payload?.fileName ?? fileResult.errorCode}-${index}`}
                            className={
                              fileResult.status === "failed" || fileResult.failedRowCount > 0
                                ? "detail-list__item detail-list__item--error"
                                : "detail-list__item"
                            }
                          >
                            <div className="ingest-result">
                              <div className="ingest-result__header">
                                <span>
                                  {fileResult.payload?.fileName ??
                                    fileResult.errorCode ??
                                    "unknown"}
                                </span>
                                <strong>{fileResult.status}</strong>
                              </div>
                              <p className="ingest-result__meta">
                                {fileResult.ingestedRowCount} ingested rows,{" "}
                                {fileResult.failedRowCount} failed rows
                              </p>
                              {fileResult.storageTarget ? (
                                <p className="ingest-result__meta">
                                  Target: {fileResult.storageTarget}
                                </p>
                              ) : null}
                              {fileResult.errorMessage ? (
                                <p className="ingest-result__error">
                                  {fileResult.errorMessage}
                                </p>
                              ) : null}
                              {fileResult.detectedColumns ? (
                                <p className="ingest-result__meta">
                                  Columns: q={fileResult.detectedColumns.questionCol ?? "n/a"},
                                  {" "}a={fileResult.detectedColumns.answerCol ?? "n/a"},
                                  {" "}d={fileResult.detectedColumns.domainCol ?? "n/a"}
                                </p>
                              ) : null}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </article>
        </section>

        <section className="tender-strip">
          <article className="panel panel--upload">
            <div className="panel__header">
              <div>
                <p className="panel__eyebrow">Autofill</p>
                <h2>Upload tender csv</h2>
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
              label="Upload tender csv"
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onFileChange={applySelectedFile}
              supportLabel="Supports .csv only"
            />

            <div className="field-grid field-grid--custom field-grid--single">
              <ThresholdControl
                label="Alignment threshold"
                max={0.99}
                min={0.1}
                step={0.01}
                value={alignmentThreshold}
                onChange={updateAlignmentThreshold}
              />
            </div>

            <button
              className="primary-button"
              disabled={processState === "loading"}
              type="button"
              onClick={() => void handleProcessClick()}
            >
              {processState === "loading" ? "Autofilling..." : "Autofill Tender"}
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
              value={String(summarySnapshot.flaggedCount)}
              detail="Rows flagged as high risk or historically inconsistent."
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
                  label={`${session.summary.totalQuestionsProcessed} questions analyzed`}
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
                      <th>Answer</th>
                      <th>Domain</th>
                      <th>Confidence</th>
                      <th>Aligned</th>
                      <th>Status</th>
                      <th>Inspect</th>
                    </tr>
                  </thead>
                  <tbody>
                    {session.questions.map((question) => (
                      <Fragment key={question.questionId}>
                        <tr className="result-row">
                          <td>{question.originalQuestion}</td>
                          <td className="result-row__answer">
                            {question.generatedAnswer || "No answer generated"}
                          </td>
                          <td>{question.domainTag || "unassigned"}</td>
                          <td>
                            <StatusBadge
                              label={question.confidenceLevel}
                              tone={confidenceTone(question.confidenceLevel)}
                            />
                          </td>
                          <td>
                            <StatusBadge
                              label={
                                question.historicalAlignmentIndicator
                                  ? "aligned"
                                  : "unaligned"
                              }
                              tone={
                                question.historicalAlignmentIndicator
                                  ? "success"
                                  : "warning"
                              }
                            />
                          </td>
                          <td>
                            <StatusBadge
                              label={question.status}
                              tone={questionStatusTone(question)}
                            />
                          </td>
                          <td>
                            <button
                              aria-expanded={expandedResultId === question.questionId}
                              aria-label={`Expand result for ${question.originalQuestion}`}
                              className="row-action"
                              type="button"
                              onClick={() =>
                                setExpandedResultId((current) =>
                                  current === question.questionId
                                    ? null
                                    : question.questionId,
                                )
                              }
                            >
                              {expandedResultId === question.questionId
                                ? "Hide details"
                                : "View details"}
                            </button>
                          </td>
                        </tr>

                        {expandedResultId === question.questionId ? (
                          <tr className="result-row__details">
                            <td colSpan={7}>
                              <div className="detail-grid">
                                <section className="detail-panel">
                                  <h4>Generated answer</h4>
                                  <p>
                                    {question.generatedAnswer ||
                                      "No answer generated for this question."}
                                  </p>
                                  {question.errorMessage ? (
                                    <>
                                      <h4>Error message</h4>
                                      <p>{question.errorMessage}</p>
                                    </>
                                  ) : null}
                                </section>

                                <section className="detail-panel">
                                  <h4>Flags</h4>
                                  <ul className="detail-list detail-list--dark">
                                    <li>
                                      <strong>high risk</strong>
                                      <span>
                                        {question.flags.highRisk ? "true" : "false"}
                                      </span>
                                    </li>
                                    <li>
                                      <strong>inconsistent response</strong>
                                      <span>
                                        {question.flags.inconsistentResponse
                                          ? "true"
                                          : "false"}
                                      </span>
                                    </li>
                                  </ul>
                                </section>

                                <section className="detail-panel">
                                  <h4>Metadata</h4>
                                  <ul className="detail-list detail-list--dark">
                                    <li>
                                      <strong>source row</strong>
                                      <span>{question.metadata.sourceRowIndex}</span>
                                    </li>
                                    <li>
                                      <strong>alignment record</strong>
                                      <span>
                                        {question.metadata.alignmentRecordId || "n/a"}
                                      </span>
                                    </li>
                                    <li>
                                      <strong>alignment score</strong>
                                      <span>
                                        {question.metadata.alignmentScore.toFixed(2)}
                                      </span>
                                    </li>
                                  </ul>
                                </section>

                                <section className="detail-panel">
                                  <h4>Extensions</h4>
                                  {Object.keys(question.extensions).length > 0 ? (
                                    <pre>
                                      {JSON.stringify(question.extensions, null, 2)}
                                    </pre>
                                  ) : (
                                    <p>
                                      No additional extensions for this question.
                                    </p>
                                  )}
                                </section>
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-state">
                Upload a csv and run autofill to populate the answer table and
                inspection panels.
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
                    label={session.summary.overallCompletionStatus}
                    tone="warning"
                  />
                ) : null}
              </div>

              {session ? (
                <>
                  <div className="metric-cluster metric-cluster--summary">
                    <MetricCard
                      eyebrow="Questions analyzed"
                      value={`${session.summary.totalQuestionsProcessed} questions analyzed`}
                      detail="Total workload included in the current run."
                    />
                    <MetricCard
                      eyebrow="Flagged items"
                      value={String(
                        session.summary.flaggedHighRiskOrInconsistentResponses,
                      )}
                      detail="Rows that need human review before submission."
                    />
                  </div>

                  <div className="summary-list">
                    <p>Completed questions: {session.summary.completedQuestions}</p>
                    <p>Failed questions: {session.summary.failedQuestions}</p>
                    <p>
                      Overall status: {session.summary.overallCompletionStatus}
                    </p>
                    <p>Request id: {session.requestId}</p>
                    <p>Session id: {session.sessionId}</p>
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
