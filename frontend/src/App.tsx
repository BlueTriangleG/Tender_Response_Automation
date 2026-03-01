import { useEffect, useMemo, useState, type DragEvent } from "react";

import { BatchUploadDropzone } from "./components/BatchUploadDropzone";
import { MetricCard } from "./components/MetricCard";
import { StatusBadge } from "./components/StatusBadge";
import { ThresholdControl } from "./components/ThresholdControl";
import { UploadDropzone } from "./components/UploadDropzone";
import {
  fetchBackendHealth,
  ingestHistoryFiles,
  processTenderWorkbook,
} from "./lib/api";
import type {
  HistoryIngestResponse,
  HistoryIngestOptions,
  TenderAutofillQuestion,
  TenderAutofillResponse,
} from "./lib/types";

type LoadState = "idle" | "loading" | "ready" | "error";
type WorkspaceTab = "repository" | "response";

const defaultKnowledgeBaseOptions: HistoryIngestOptions = {
  outputFormat: "json",
  similarityThreshold: 0.72,
};
const defaultAlignmentThreshold = 0.5;

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

function shouldShowConfidence(question: TenderAutofillQuestion) {
  return question.status === "completed" && question.confidenceLevel !== null;
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

function riskTone(level: "high" | "medium" | "low") {
  if (level === "high") {
    return "danger" as const;
  }

  if (level === "medium") {
    return "warning" as const;
  }

  return "success" as const;
}

function isSupportedTenderWorkbook(file: File) {
  const normalizedName = file.name.toLowerCase();

  return normalizedName.endsWith(".csv") || normalizedName.endsWith(".xlsx");
}

function formatStatusLabel(value: string) {
  if (!value) {
    return "Pending";
  }

  return value
    .replaceAll(/[_-]+/g, " ")
    .replaceAll(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatGroundingStatus(value: string) {
  return formatStatusLabel(value || "unknown");
}

function summarizeAnswer(answer: string) {
  const trimmed = answer.trim();

  if (!trimmed) {
    return "No answer generated";
  }

  if (trimmed.length <= 180) {
    return trimmed;
  }

  return `${trimmed.slice(0, 177)}...`;
}

function formatWorkflowDuration(durationMs: number | null) {
  if (durationMs == null) {
    return "Pending";
  }

  return `${(durationMs / 1000).toFixed(2)}s`;
}

function reviewSignalSummary(question: TenderAutofillQuestion) {
  const signals: string[] = [];

  if (question.flags.highRisk) {
    signals.push("High-risk wording");
  }

  if (question.flags.inconsistentResponse) {
    signals.push("Potential historical inconsistency");
  }

  if (!question.historicalAlignmentIndicator) {
    signals.push("Needs repository review");
  }

  if (signals.length === 0) {
    return "No additional review signals on this answer.";
  }

  return signals.join(". ") + ".";
}

function App() {
  // The dashboard keeps network state local because the interaction surface is
  // small and the take-home brief explicitly does not need a state library.
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [session, setSession] = useState<TenderAutofillResponse | null>(null);
  const [activeQuestionId, setActiveQuestionId] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState("checking");
  const [processState, setProcessState] = useState<LoadState>("idle");
  const [knowledgeBaseState, setKnowledgeBaseState] = useState<LoadState>("idle");
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceTab>("repository");
  const [isDragActive, setIsDragActive] = useState(false);
  const [screenMessage, setScreenMessage] = useState(
    "Waiting for a tender workbook.",
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
  const [workflowDurationMs, setWorkflowDurationMs] = useState<number | null>(
    null,
  );

  useEffect(() => {
    let active = true;

    async function loadDashboardChrome() {
      try {
        const health = await fetchBackendHealth();

        if (!active) {
          return;
        }

        setHealthStatus(health.status);
      } catch (error) {
        if (!active) {
          return;
        }

        setHealthStatus("offline");
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
        unanswered: 0,
        failed: 0,
        label: processState === "loading" ? "processing" : "idle",
      };
    }

    return {
      total: session.summary.totalQuestionsProcessed,
      completed: session.summary.completedQuestions,
      unanswered: session.summary.unansweredQuestions,
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
    setWorkflowDurationMs(null);

    if (file && !isSupportedTenderWorkbook(file)) {
      setSelectedFile(null);
      setScreenMessage("Autofill only accepts .csv or .xlsx files.");
      return;
    }

    setSelectedFile(file);

    // Routing every file-selection path through one helper keeps drag-and-drop
    // and manual browse interactions perfectly aligned.
    if (file) {
      setScreenMessage(`${file.name} staged and ready for processing.`);
      return;
    }

    setScreenMessage("Waiting for a tender workbook.");
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
      setScreenMessage("Select a tender CSV or XLSX file before starting the run.");
      return;
    }

    const startedAt = Date.now();

    setProcessState("loading");
    setWorkflowDurationMs(null);
    setScreenMessage(`Autofilling ${selectedFile.name}...`);

    try {
      const nextSession = await processTenderWorkbook(selectedFile, {
        alignmentThreshold,
      });
      const durationMs = Math.max(0, Date.now() - startedAt);

      setSession(nextSession);
      setActiveQuestionId(null);
      setProcessState("ready");
      setWorkflowDurationMs(durationMs);
      setScreenMessage(
        `${nextSession.summary.totalQuestionsProcessed} questions analyzed for ${selectedFile.name}.`,
      );
    } catch (error) {
      const durationMs = Math.max(0, Date.now() - startedAt);

      setProcessState("error");
      setWorkflowDurationMs(durationMs);
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
                result.confidenceLevel ?? "",
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

  const activeQuestion = useMemo(
    () =>
      activeQuestionId == null
        ? null
        : session?.questions.find((question) => question.questionId === activeQuestionId) ??
          null,
    [activeQuestionId, session],
  );

  useEffect(() => {
    if (!activeQuestion) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;

    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [activeQuestion]);

  return (
    <div className="app-shell">
      <div className="app-shell__mesh" aria-hidden="true" />

      <main className="dashboard">
        <header className="app-header">
          <div className="app-header__brand">
            <p className="app-header__eyebrow">Tender workbench</p>
            <h1>Tender Response Automation</h1>
            <p className="app-header__subcopy">
              Separate the knowledge repository workflow from the live response workflow.
            </p>
          </div>
        </header>

        {healthStatus !== "ok" && healthStatus !== "checking" ? (
          <section className="health-banner" aria-label="Backend health warning">
            <StatusBadge label={`Backend health: ${healthStatus}`} tone="danger" />
            <p>The backend is not healthy. Uploads or response generation may fail.</p>
          </section>
        ) : null}

        <section className="workspace-tabs">
          <div aria-label="Workspace modules" className="tablist" role="tablist">
            <button
              aria-controls="repository-panel"
              aria-selected={activeWorkspace === "repository"}
              className={
                activeWorkspace === "repository"
                  ? "tab-button tab-button--active"
                  : "tab-button"
              }
              id="repository-tab"
              role="tab"
              type="button"
              onClick={() => setActiveWorkspace("repository")}
            >
              Tender Repository
            </button>
            <button
              aria-controls="response-panel"
              aria-selected={activeWorkspace === "response"}
              className={
                activeWorkspace === "response"
                  ? "tab-button tab-button--active"
                  : "tab-button"
              }
              id="response-tab"
              role="tab"
              type="button"
              onClick={() => setActiveWorkspace("response")}
            >
              Tender Response
            </button>
          </div>
        </section>

        {activeWorkspace === "repository" ? (
          <section
            aria-labelledby="knowledge-base-builder-title"
            className="workspace-panel"
            id="repository-panel"
            role="tabpanel"
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

              <div className="workspace-intro">
                <p className="workspace-intro__title">Tender Repository</p>
                <p className="workspace-intro__copy">
                  Upload historical tender files, review the queued batch, and send the
                  repository update to the ingest API in one step.
                </p>
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
                                fileResult.status === "failed" ||
                                fileResult.failedRowCount > 0
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
                                    Columns: q=
                                    {fileResult.detectedColumns.questionCol ?? "n/a"}, a=
                                    {fileResult.detectedColumns.answerCol ?? "n/a"}, d=
                                    {fileResult.detectedColumns.domainCol ?? "n/a"}
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
        ) : (
          <section
            aria-labelledby="tender-response-title"
            className="workspace-panel workspace-panel--response"
            id="response-panel"
            role="tabpanel"
          >
            <div className="response-shell">
              <article className="panel panel--upload">
                <div className="panel__header">
                  <div>
                    <p className="panel__eyebrow">Autofill</p>
                    <h2 id="tender-response-title">Tender response</h2>
                  </div>
                  <StatusBadge
                    label={selectedFile ? "file ready" : "awaiting file"}
                    tone={selectedFile ? "success" : "neutral"}
                  />
                </div>

                <div className="workspace-intro">
                  <p className="workspace-intro__title">Tender Response</p>
                  <p className="workspace-intro__copy">
                    Upload a tender questionnaire in CSV or XLSX format, send it to
                    the response workflow, and review generated answers in a clean
                    table.
                  </p>
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
                  supportLabel="Supports .csv and .xlsx"
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

              <section className="response-dashboard">
                <article className="panel panel--summary-strip">
                  <div className="panel__header">
                    <div>
                      <p className="panel__eyebrow">Run snapshot</p>
                      <h2>Response dashboard</h2>
                    </div>
                    <StatusBadge
                      label={formatStatusLabel(summarySnapshot.overallStatus)}
                      tone={processState === "error" ? "danger" : "warning"}
                    />
                  </div>

                  <div className="summary-cards">
                    <MetricCard
                      eyebrow="Batch state"
                      value={formatStatusLabel(progressSnapshot.label)}
                      detail={screenMessage}
                    />
                    <MetricCard
                      eyebrow="Questions analyzed"
                      value={String(progressSnapshot.total)}
                      detail="Rows processed in the current tender response run."
                    />
                    <MetricCard
                      eyebrow="Completed"
                      value={String(progressSnapshot.completed)}
                      detail="Generated answers ready for review."
                    />
                    <MetricCard
                      eyebrow="Flagged"
                      value={String(summarySnapshot.flaggedCount)}
                      detail="Questions that need extra human review."
                    />
                    <MetricCard
                      eyebrow="Workflow duration"
                      value={formatWorkflowDuration(workflowDurationMs)}
                      detail="Measured from Autofill Tender click to API response."
                    />
                    <MetricCard
                      eyebrow="Unanswered"
                      value={String(progressSnapshot.unanswered)}
                      detail="Questions without a generated answer yet."
                    />
                    <MetricCard
                      eyebrow="Failed"
                      value={String(progressSnapshot.failed)}
                      detail="Questions that did not produce a usable answer."
                    />
                  </div>
                </article>

                <article className="panel panel--results">
                  <div className="panel__header">
                    <div>
                      <p className="panel__eyebrow">Generated answers</p>
                      <h2>Question Results</h2>
                    </div>
                    {session ? (
                      <StatusBadge
                        label={`${session.summary.totalQuestionsProcessed} Questions Analyzed`}
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
                            <th>Generated answer</th>
                            <th>Details</th>
                          </tr>
                        </thead>
                        <tbody>
                          {session.questions.map((question) => (
                            <tr className="result-row" key={question.questionId}>
                              <td className="result-row__question">
                                <p className="result-row__primary">
                                  {question.originalQuestion}
                                </p>
                                <div className="result-row__meta">
                                  <StatusBadge
                                    label={formatStatusLabel(question.status)}
                                    tone={questionStatusTone(question)}
                                  />
                                  {shouldShowConfidence(question) ? (
                                    <StatusBadge
                                      label={formatStatusLabel(question.confidenceLevel ?? "")}
                                      tone={confidenceTone(question.confidenceLevel)}
                                    />
                                  ) : null}
                                </div>
                              </td>
                              <td className="result-row__answer">
                                {summarizeAnswer(question.generatedAnswer)}
                              </td>
                              <td className="result-row__actions">
                                <button
                                  aria-haspopup="dialog"
                                  aria-label={`Open details for ${question.originalQuestion}`}
                                  className="row-action"
                                  type="button"
                                  onClick={() => setActiveQuestionId(question.questionId)}
                                >
                                  View details
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="empty-state">
                      Upload a CSV or XLSX file and run autofill to populate the answer table.
                    </p>
                  )}
                </article>

                {session ? (
                  <article className="panel panel--summary">
                    <div className="panel__header">
                      <div>
                        <p className="panel__eyebrow">Run overview</p>
                        <h2>Summary</h2>
                      </div>
                      <StatusBadge
                        label={formatStatusLabel(session.summary.overallCompletionStatus)}
                        tone="warning"
                      />
                    </div>

                    <div className="summary-list">
                      <p>Source file: {session.sourceFileName}</p>
                      <p>
                        Questions analyzed: {session.summary.totalQuestionsProcessed}
                      </p>
                      <p>Completed questions: {session.summary.completedQuestions}</p>
                      <p>Failed questions: {session.summary.failedQuestions}</p>
                      <p>
                        Flagged for review:{" "}
                        {
                          session.summary
                            .flaggedHighRiskOrInconsistentResponses
                        }
                      </p>
                      <p>
                        Unanswered questions: {session.summary.unansweredQuestions}
                      </p>
                      <p>
                        Workflow duration: {formatWorkflowDuration(workflowDurationMs)}
                      </p>
                      <p>
                        Overall status:{" "}
                        {formatStatusLabel(session.summary.overallCompletionStatus)}
                      </p>
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
                ) : null}
              </section>
            </div>
          </section>
        )}

        {activeQuestion ? (
          <div
            className="modal-backdrop"
            onClick={() => setActiveQuestionId(null)}
          >
            <section
              aria-labelledby="autofill-details-title"
              aria-modal="true"
              className="details-modal"
              role="dialog"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="details-modal__header">
                <div>
                  <p className="panel__eyebrow">Autofill review</p>
                  <h2 id="autofill-details-title">Autofill details</h2>
                </div>
                <button
                  aria-label="Close details"
                  className="secondary-button"
                  type="button"
                  onClick={() => setActiveQuestionId(null)}
                >
                  Close
                </button>
              </div>

              <div className="details-modal__summary">
                <StatusBadge
                  label={formatStatusLabel(activeQuestion.status)}
                  tone={questionStatusTone(activeQuestion)}
                />
                {shouldShowConfidence(activeQuestion) ? (
                  <StatusBadge
                    label={formatStatusLabel(activeQuestion.confidenceLevel ?? "")}
                    tone={confidenceTone(activeQuestion.confidenceLevel)}
                  />
                ) : null}
                <StatusBadge
                  label={formatGroundingStatus(activeQuestion.groundingStatus)}
                  tone={
                    activeQuestion.groundingStatus === "grounded"
                      ? "success"
                      : activeQuestion.groundingStatus
                            .toLowerCase()
                            .includes("ungrounded")
                        ? "danger"
                        : "warning"
                  }
                />
                <StatusBadge
                  label={
                    activeQuestion.historicalAlignmentIndicator
                      ? "Historically Aligned"
                      : "Needs Review"
                  }
                  tone={
                    activeQuestion.historicalAlignmentIndicator
                      ? "success"
                      : "warning"
                  }
                />
              </div>

              <div className="details-modal__grid">
                <section className="details-card details-card--wide">
                  <h3>Original question</h3>
                  <p>{activeQuestion.originalQuestion}</p>
                </section>

                <section className="details-card details-card--wide">
                  <h3>Generated answer</h3>
                  <p>
                    {activeQuestion.generatedAnswer || "No answer generated for this question."}
                  </p>
                </section>

                {activeQuestion.errorMessage ? (
                  <section className="details-card details-card--wide details-card--alert">
                    <h3>Error message</h3>
                    <p>{activeQuestion.errorMessage}</p>
                  </section>
                ) : null}

                {shouldShowConfidence(activeQuestion) ? (
                  <section className="details-card">
                    <h3>Confidence</h3>
                    <div className="details-card__header">
                      <StatusBadge
                        label={formatStatusLabel(activeQuestion.confidenceLevel ?? "")}
                        tone={confidenceTone(activeQuestion.confidenceLevel)}
                      />
                    </div>
                    <p>
                      {activeQuestion.confidenceReason ||
                        "No confidence rationale was returned for this answer."}
                    </p>
                  </section>
                ) : null}

                <section className="details-card">
                  <h3>Risk review</h3>
                  <div className="details-card__header">
                    <StatusBadge
                      label={formatStatusLabel(activeQuestion.risk?.level ?? "low")}
                      tone={riskTone(activeQuestion.risk?.level ?? "low")}
                    />
                  </div>
                  <p>
                    {activeQuestion.risk?.reason ||
                      "No elevated risk was returned for this answer."}
                  </p>
                </section>

                <section className="details-card">
                  <h3>Review signals</h3>
                  <div className="details-card__stack">
                    <p>
                      <strong>Domain:</strong> {activeQuestion.domainTag || "unassigned"}
                    </p>
                    <p>
                      <strong>Historical alignment:</strong>{" "}
                      {activeQuestion.historicalAlignmentIndicator
                        ? "Consistent with repository history"
                        : "Manual review recommended"}
                    </p>
                    <p>
                      <strong>Alignment score:</strong>{" "}
                      {activeQuestion.alignmentScore == null
                        ? "n/a"
                        : activeQuestion.alignmentScore.toFixed(2)}
                    </p>
                    <p>{reviewSignalSummary(activeQuestion)}</p>
                  </div>
                </section>

                {activeQuestion.references.length > 0 ? (
                  <section className="details-card details-card--wide">
                    <h3>Reference matches</h3>
                    <div className="reference-list">
                      {activeQuestion.references.map((reference, index) => (
                        <article
                          className="reference-card"
                          key={`${reference.sourceDoc}-${reference.matchedQuestion}-${index}`}
                        >
                          <div className="reference-card__header">
                            <strong>{reference.sourceDoc || "Unknown source"}</strong>
                            <StatusBadge
                              label={
                                reference.usedForAnswer
                                  ? "Used For Answer"
                                  : "Reference Only"
                              }
                              tone={reference.usedForAnswer ? "success" : "neutral"}
                            />
                          </div>

                          <div className="reference-card__body">
                            <div>
                              <h4>Matched question</h4>
                              <p>
                                {reference.matchedQuestion ||
                                  "No matched question available."}
                              </p>
                            </div>
                            <div>
                              <h4>Matched answer</h4>
                              <p>
                                {reference.matchedAnswer ||
                                  "No matched answer available."}
                              </p>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                ) : null}
              </div>
            </section>
          </div>
        ) : null}
      </main>
    </div>
  );
}

export default App;
