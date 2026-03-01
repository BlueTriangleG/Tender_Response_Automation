import type {
  BackendHealth,
  HistoryIngestResponse,
  HistoryIngestOptions,
  TenderAutofillOptions,
  TenderAutofillResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function normalizeHistoryIngestResponse(
  payload: Record<string, unknown>,
): HistoryIngestResponse {
  return {
    requestId: String(payload.request_id ?? ""),
    totalFileCount: Number(payload.total_file_count ?? 0),
    processedFileCount: Number(payload.processed_file_count ?? 0),
    failedFileCount: Number(payload.failed_file_count ?? 0),
    requestOptions: {
      outputFormat:
        payload.request_options &&
        typeof payload.request_options === "object" &&
        "output_format" in payload.request_options
          ? String(payload.request_options.output_format ?? "json") === "excel"
            ? "excel"
            : "json"
          : "json",
      similarityThreshold:
        payload.request_options &&
        typeof payload.request_options === "object" &&
        "similarity_threshold" in payload.request_options
          ? Number(payload.request_options.similarity_threshold ?? 0.72)
          : 0.72,
    },
    files: Array.isArray(payload.files)
      ? payload.files.map((item) => {
          const file = (item ?? {}) as Record<string, unknown>;
          const payloadValue =
            file.payload && typeof file.payload === "object"
              ? (file.payload as Record<string, unknown>)
              : null;
          const detectedColumnsValue =
            file.detected_columns && typeof file.detected_columns === "object"
              ? (file.detected_columns as Record<string, unknown>)
              : null;

          return {
            status: file.status === "failed" ? "failed" : "processed",
            payload: payloadValue
              ? {
                  fileName: String(payloadValue.file_name ?? ""),
                  extension: String(payloadValue.extension ?? ""),
                  contentType:
                    payloadValue.content_type == null
                      ? null
                      : String(payloadValue.content_type),
                  sizeBytes: Number(payloadValue.size_bytes ?? 0),
                  parsedKind: String(payloadValue.parsed_kind ?? ""),
                  rawText: String(payloadValue.raw_text ?? ""),
                  structuredData: payloadValue.structured_data ?? null,
                  rowCount:
                    payloadValue.row_count == null
                      ? null
                      : Number(payloadValue.row_count),
                  warnings: Array.isArray(payloadValue.warnings)
                    ? payloadValue.warnings.map((warning) => String(warning))
                    : [],
                }
              : null,
            errorCode: file.error_code == null ? null : String(file.error_code),
            errorMessage:
              file.error_message == null ? null : String(file.error_message),
            detectedColumns: detectedColumnsValue
              ? {
                  questionCol:
                    detectedColumnsValue.question_col == null
                      ? null
                      : String(detectedColumnsValue.question_col),
                  answerCol:
                    detectedColumnsValue.answer_col == null
                      ? null
                      : String(detectedColumnsValue.answer_col),
                  domainCol:
                    detectedColumnsValue.domain_col == null
                      ? null
                      : String(detectedColumnsValue.domain_col),
                }
              : null,
            ingestedRowCount: Number(file.ingested_row_count ?? 0),
            failedRowCount: Number(file.failed_row_count ?? 0),
            storageTarget:
              file.storage_target == null ? null : String(file.storage_target),
          };
        })
      : [],
  };
}

function normalizeTenderAutofillResponse(
  payload: Record<string, unknown>,
): TenderAutofillResponse {
  const summaryValue =
    payload.summary && typeof payload.summary === "object"
      ? (payload.summary as Record<string, unknown>)
      : null;

  return {
    requestId: String(payload.request_id ?? ""),
    sessionId: String(payload.session_id ?? ""),
    sourceFileName: String(payload.source_file_name ?? ""),
    totalQuestionsProcessed: Number(payload.total_questions_processed ?? 0),
    questions: Array.isArray(payload.questions)
      ? payload.questions.map((item) => {
          const question = (item ?? {}) as Record<string, unknown>;
          const flags =
            question.flags && typeof question.flags === "object"
              ? (question.flags as Record<string, unknown>)
              : {};
          const metadata =
            question.metadata && typeof question.metadata === "object"
              ? (question.metadata as Record<string, unknown>)
              : {};
          const extensions =
            question.extensions && typeof question.extensions === "object"
              ? (question.extensions as Record<string, unknown>)
              : {};
          const references = Array.isArray(question.references)
            ? question.references
            : [];
          const risk =
            question.risk && typeof question.risk === "object"
              ? (question.risk as Record<string, unknown>)
              : null;

          return {
            questionId: String(question.question_id ?? ""),
            originalQuestion: String(question.original_question ?? ""),
            generatedAnswer: String(question.generated_answer ?? ""),
            domainTag: String(question.domain_tag ?? ""),
            confidenceLevel:
              question.confidence_level === "low" ||
              question.confidence_level === "medium" ||
              question.confidence_level === "high"
                ? question.confidence_level
                : null,
            confidenceReason:
              question.confidence_reason == null
                ? null
                : String(question.confidence_reason),
            historicalAlignmentIndicator: Boolean(
              question.historical_alignment_indicator,
            ),
            alignmentScore:
              metadata.alignment_score == null
                ? null
                : Number(metadata.alignment_score),
            status: String(question.status ?? ""),
            groundingStatus: String(question.grounding_status ?? ""),
            flags: {
              highRisk: Boolean(flags.high_risk),
              inconsistentResponse: Boolean(flags.inconsistent_response),
              hasConflict: Boolean(flags.has_conflict),
            },
            risk: risk
              ? {
                  level:
                    risk.level === "high" ||
                    risk.level === "medium" ||
                    risk.level === "low"
                      ? risk.level
                      : "low",
                  reason: String(risk.reason ?? ""),
                }
              : null,
            references: references.map((reference) => {
              const value = (reference ?? {}) as Record<string, unknown>;

              return {
                sourceDoc: String(value.source_doc ?? ""),
                matchedQuestion: String(value.matched_question ?? ""),
                matchedAnswer: String(value.matched_answer ?? ""),
                usedForAnswer: Boolean(value.used_for_answer),
              };
            }),
            errorMessage:
              question.error_message == null ? null : String(question.error_message),
            extensions: {
              ...extensions,
              conflicts: Array.isArray(extensions.conflicts)
                ? extensions.conflicts.map((item) => {
                    const conflict = (item ?? {}) as Record<string, unknown>;

                    return {
                      conflictingQuestionId: String(
                        conflict.conflicting_question_id ?? "",
                      ),
                      conflictingQuestion: String(
                        conflict.conflicting_question ?? "",
                      ),
                      reason: String(conflict.reason ?? ""),
                      severity:
                        conflict.severity === "high" ||
                        conflict.severity === "medium" ||
                        conflict.severity === "low"
                          ? conflict.severity
                          : "low",
                    };
                  })
                : [],
            },
          };
        })
      : [],
    summary: summaryValue
      ? {
          totalQuestionsProcessed: Number(
            summaryValue.total_questions_processed ?? 0,
          ),
          flaggedHighRiskOrInconsistentResponses: Number(
            summaryValue.flagged_high_risk_or_inconsistent_responses ?? 0,
          ),
          overallCompletionStatus: String(
            summaryValue.overall_completion_status ?? "pending",
          ),
          completedQuestions: Number(summaryValue.completed_questions ?? 0),
          unansweredQuestions: Number(summaryValue.unanswered_questions ?? 0),
          failedQuestions: Number(summaryValue.failed_questions ?? 0),
          conflictCount: Number(summaryValue.conflict_count ?? 0),
        }
      : {
          totalQuestionsProcessed: 0,
          flaggedHighRiskOrInconsistentResponses: 0,
          overallCompletionStatus: "pending",
          completedQuestions: 0,
          unansweredQuestions: 0,
          failedQuestions: 0,
          conflictCount: 0,
        },
  };
}

async function extractErrorMessage(response: Response, fallbackMessage: string) {
  try {
    const payload = (await response.json()) as Record<string, unknown>;

    if (typeof payload.detail === "string") {
      return payload.detail;
    }

    if (Array.isArray(payload.detail) && payload.detail.length > 0) {
      const firstItem = payload.detail[0] as Record<string, unknown>;

      if (typeof firstItem.msg === "string") {
        return firstItem.msg;
      }
    }
  } catch {
    return fallbackMessage;
  }

  return fallbackMessage;
}

// Health is the only live backend contract available today, so the dashboard
// fetches it directly to prove that the frontend is wired to the real API.
export async function fetchBackendHealth(): Promise<BackendHealth> {
  const response = await fetch(`${API_BASE_URL}/api/health`);

  if (!response.ok) {
    throw new Error("Backend health request failed.");
  }

  const payload = (await response.json()) as Partial<BackendHealth>;

  // The backend contract is intentionally tiny. Normalizing it here keeps the
  // UI resilient to harmless casing differences while still rejecting malformed
  // payloads instead of silently drifting into a broken state.
  if (typeof payload.status !== "string") {
    throw new Error("Backend health payload is missing a status field.");
  }

  return {
    status: payload.status.trim().toLowerCase(),
  };
}

export async function ingestHistoryFiles(
  files: File[],
  options: Partial<HistoryIngestOptions> = {},
): Promise<HistoryIngestResponse> {
  const formData = new FormData();

  for (const file of files) {
    formData.append("files", file);
  }

  formData.append("outputFormat", options.outputFormat ?? "json");
  formData.append(
    "similarityThreshold",
    String(options.similarityThreshold ?? 0.72),
  );

  const response = await fetch(`${API_BASE_URL}/api/ingest/history`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Knowledge base ingest request failed.");
  }

  const payload = (await response.json()) as Record<string, unknown>;

  return normalizeHistoryIngestResponse(payload);
}

export async function processTenderWorkbook(
  file: File,
  options: TenderAutofillOptions,
): Promise<TenderAutofillResponse> {
  const normalizedName = file.name.toLowerCase();
  if (
    !normalizedName.endsWith(".csv") &&
    !normalizedName.endsWith(".xlsx")
  ) {
    throw new Error("Autofill only accepts .csv or .xlsx files.");
  }

  const formData = new FormData();

  formData.append("file", file);
  formData.append("alignmentThreshold", String(options.alignmentThreshold));

  if (options.sessionId) {
    formData.append("sessionId", options.sessionId);
  }

  const response = await fetch(`${API_BASE_URL}/api/tender/respond`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Tender autofill request failed."),
    );
  }

  const payload = (await response.json()) as Record<string, unknown>;

  return normalizeTenderAutofillResponse(payload);
}
