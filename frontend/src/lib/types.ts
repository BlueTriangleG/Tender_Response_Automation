// This file centralizes the dashboard contracts so the UI, tests, and API
// helpers all read from the same vocabulary.

export type BackendHealth = {
  status: string;
};

export type OutputFormat = "json" | "excel";

export type DomainBreakdown = {
  domain: string;
  count: number;
};

export type HistoryStatus = {
  itemCount: number;
  lastUpdated: string;
  domainDistribution: DomainBreakdown[];
};

export type HistoryIngestRequestOptions = {
  outputFormat: OutputFormat;
  similarityThreshold: number;
};

export type ParsedHistoryFilePayload = {
  fileName: string;
  extension: string;
  contentType: string | null;
  sizeBytes: number;
  parsedKind: string;
  rawText: string;
  structuredData: unknown;
  rowCount: number | null;
  warnings: string[];
};

export type DetectedColumns = {
  questionCol: string | null;
  answerCol: string | null;
  domainCol: string | null;
};

export type ProcessedHistoryFileResult = {
  status: "processed" | "failed";
  payload: ParsedHistoryFilePayload | null;
  errorCode: string | null;
  errorMessage: string | null;
  detectedColumns: DetectedColumns | null;
  ingestedRowCount: number;
  failedRowCount: number;
  storageTarget: string | null;
};

export type HistoryIngestResponse = {
  requestId: string;
  totalFileCount: number;
  processedFileCount: number;
  failedFileCount: number;
  requestOptions: HistoryIngestRequestOptions;
  files: ProcessedHistoryFileResult[];
};

export type TenderAutofillQuestionFlags = {
  highRisk: boolean;
  inconsistentResponse: boolean;
};

export type TenderAutofillQuestionRisk = {
  level: "high" | "medium" | "low";
  reason: string;
};

export type TenderAutofillQuestionReference = {
  sourceDoc: string;
  matchedQuestion: string;
  matchedAnswer: string;
  usedForAnswer: boolean;
};

export type TenderAutofillQuestion = {
  questionId: string;
  originalQuestion: string;
  generatedAnswer: string;
  domainTag: string;
  confidenceLevel: "high" | "medium" | "low" | null;
  confidenceReason: string | null;
  historicalAlignmentIndicator: boolean;
  alignmentScore: number | null;
  status: string;
  groundingStatus: string;
  flags: TenderAutofillQuestionFlags;
  risk: TenderAutofillQuestionRisk | null;
  references: TenderAutofillQuestionReference[];
  errorMessage: string | null;
  extensions: Record<string, unknown>;
};

export type TenderAutofillSummary = {
  totalQuestionsProcessed: number;
  flaggedHighRiskOrInconsistentResponses: number;
  overallCompletionStatus: string;
  completedQuestions: number;
  unansweredQuestions: number;
  failedQuestions: number;
};

export type TenderAutofillResponse = {
  requestId: string;
  sessionId: string;
  sourceFileName: string;
  totalQuestionsProcessed: number;
  questions: TenderAutofillQuestion[];
  summary: TenderAutofillSummary;
};

export type HistoricalMatch = {
  title: string;
  source: string;
  similarity: number;
};

export type ResultStatus = "success" | "warning" | "failed";

export type AlignmentStatus = "aligned" | "inconsistent" | "partial";

export type RiskLevel = "low" | "medium" | "high";

export type TenderQuestionResult = {
  id: string;
  question: string;
  domain: string;
  alignment: AlignmentStatus;
  confidence: number;
  risk: RiskLevel;
  status: ResultStatus;
  generatedAnswer: string;
  riskFlags: string[];
  errorMessage?: string;
  historicalMatches: HistoricalMatch[];
};

export type TenderSummary = {
  totalQuestions: number;
  successCount: number;
  failedCount: number;
  highRiskCount: number;
  inconsistentCount: number;
  overallStatus: string;
};

export type TenderSession = {
  sessionId: string;
  fileName: string;
  summary: TenderSummary;
  results: TenderQuestionResult[];
};

export type HistoryIngestOptions = {
  outputFormat: OutputFormat;
  similarityThreshold: number;
};

export type TenderAutofillOptions = {
  alignmentThreshold: number;
  sessionId?: string | null;
};

export type ProcessOptions = HistoryIngestOptions;
