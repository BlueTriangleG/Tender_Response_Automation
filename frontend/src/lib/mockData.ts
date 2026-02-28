import type { HistoryStatus, TenderSession } from "./types";

// The mock history payload stands in for the future backend endpoint and gives
// the dashboard a stable dataset to visualize during interviews.
export const mockHistoryStatus: HistoryStatus = {
  itemCount: 124,
  lastUpdated: "2026-02-27T22:14:00Z",
  domainDistribution: [
    { domain: "Transport", count: 52 },
    { domain: "Utilities", count: 36 },
    { domain: "Public Works", count: 24 },
    { domain: "Education", count: 12 },
  ],
};

// The mock session intentionally includes one warning and one failure so the
// UI can demonstrate risk handling, partial success, and failure isolation.
export const mockTenderSession: TenderSession = {
  sessionId: "session-demo-transport-001",
  fileName: "transport-tender.xlsx",
  summary: {
    totalQuestions: 3,
    successCount: 2,
    failedCount: 1,
    highRiskCount: 1,
    inconsistentCount: 1,
    overallStatus: "partial success",
  },
  results: [
    {
      id: "submission-readiness",
      question: "Submission readiness",
      domain: "Transport",
      alignment: "aligned",
      confidence: 0.82,
      risk: "low",
      status: "success",
      generatedAnswer:
        "Our delivery approach is already aligned to the agency's staged submission plan, with governance checkpoints mapped to each milestone.",
      riskFlags: [],
      historicalMatches: [
        {
          title: "Regional Rail Submission Pack",
          source: "transport/rail/regional-rail-2025.xlsx",
          similarity: 0.72,
        },
        {
          title: "Metro Platform Upgrade Response",
          source: "transport/metro/platform-upgrade-2024.xlsx",
          similarity: 0.66,
        },
      ],
    },
    {
      id: "safety-assurance",
      question: "Safety assurance controls",
      domain: "Public Works",
      alignment: "partial",
      confidence: 0.68,
      risk: "high",
      status: "warning",
      generatedAnswer:
        "Safety procedures are documented, but the tender requests a named escalation owner that does not appear in the current knowledge base.",
      riskFlags: [
        "Missing named escalation owner",
        "Needs human confirmation before submission",
      ],
      historicalMatches: [
        {
          title: "Bridge Retrofit Method Statement",
          source: "public-works/bridge/retrofit-method-2025.xlsx",
          similarity: 0.58,
        },
      ],
    },
    {
      id: "pricing-schedule",
      question: "Pricing schedule assumptions",
      domain: "Utilities",
      alignment: "inconsistent",
      confidence: 0.41,
      risk: "medium",
      status: "failed",
      generatedAnswer: "",
      riskFlags: ["Conflicting assumptions detected across historical entries"],
      errorMessage:
        "The source examples contain incompatible commercial assumptions. Human review is required.",
      historicalMatches: [
        {
          title: "Water Network Maintenance Bid",
          source: "utilities/water/maintenance-bid-2025.xlsx",
          similarity: 0.49,
        },
      ],
    },
  ],
};
