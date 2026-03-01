import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const mockHealthResponse = {
  status: "ok",
};

const successfulIngestResponse = {
  request_id: "req-123",
  total_file_count: 2,
  processed_file_count: 2,
  failed_file_count: 0,
  request_options: {
    output_format: "json",
    similarity_threshold: 0.72,
  },
  files: [
    {
      status: "processed",
      payload: {
        file_name: "history-a.json",
        extension: ".json",
        content_type: "application/json",
        size_bytes: 12,
        parsed_kind: "json",
        raw_text: "{\"a\":1}",
        structured_data: { a: 1 },
        row_count: 1,
        warnings: [],
      },
      error_code: null,
      error_message: null,
      detected_columns: {
        question_col: "question",
        answer_col: "answer",
        domain_col: "domain",
      },
      ingested_row_count: 1,
      failed_row_count: 0,
      storage_target: "lancedb://qa_records",
    },
    {
      status: "processed",
      payload: {
        file_name: "history-b.md",
        extension: ".md",
        content_type: "text/markdown",
        size_bytes: 8,
        parsed_kind: "markdown",
        raw_text: "# Notes",
        structured_data: null,
        row_count: null,
        warnings: [],
      },
      error_code: null,
      error_message: null,
      detected_columns: {
        question_col: null,
        answer_col: null,
        domain_col: "domain",
      },
      ingested_row_count: 4,
      failed_row_count: 0,
      storage_target: "lancedb://document_records",
    },
  ],
};

const successfulTenderResponse = {
  request_id: "req-tender-123",
  session_id: "session-123",
  source_file_name: "tender.csv",
  total_questions_processed: 2,
  questions: [
    {
      question_id: "q-001",
      original_question: "Do you support TLS 1.2 or above?",
      generated_answer:
        "Yes. The platform enforces TLS 1.2+ for all client-facing traffic.",
      domain_tag: "security",
      confidence_level: "high",
      confidence_reason:
        "The answer is directly supported by multiple prior security submissions.",
      historical_alignment_indicator: true,
      status: "completed",
      grounding_status: "grounded",
      flags: {
        high_risk: false,
        inconsistent_response: false,
        has_conflict: false,
      },
      risk: {
        level: "low",
        reason: "This is a standard platform capability with no unusual commitments.",
      },
      metadata: {
        source_row_index: 0,
        alignment_record_id: "qa-001",
        alignment_score: 0.94,
      },
      references: [
        {
          alignment_record_id: "qa-001",
          alignment_score: 0.94,
          source_doc: "security-history.csv",
          matched_question: "Do you support TLS 1.2+?",
          matched_answer: "Yes. TLS 1.2+ is enforced for all external traffic.",
          used_for_answer: true,
        },
      ],
      error_message: null,
      extensions: {},
    },
    {
      question_id: "q-002",
      original_question: "Describe your data residency controls.",
      generated_answer: "",
      domain_tag: "compliance",
      confidence_level: "medium",
      confidence_reason:
        "There is some related historical material, but the wording is broader than the closest matches.",
      historical_alignment_indicator: false,
      status: "failed",
      grounding_status: "partially_grounded",
      flags: {
        high_risk: true,
        inconsistent_response: true,
        has_conflict: false,
      },
      risk: {
        level: "high",
        reason: "The answer could overstate contractual hosting guarantees without human review.",
      },
      metadata: {
        source_row_index: 1,
        alignment_record_id: "qa-002",
        alignment_score: 0.41,
      },
      references: [
        {
          alignment_record_id: "qa-002",
          alignment_score: 0.41,
          source_doc: "compliance-history.csv",
          matched_question: "Describe data residency controls.",
          matched_answer: "Regional hosting is available with contract-specific controls.",
          used_for_answer: false,
        },
        {
          alignment_record_id: "qa-003",
          alignment_score: 0.38,
          source_doc: "regional-controls.csv",
          matched_question: "What hosting residency options do you provide?",
          matched_answer: "Regional controls are available by deployment profile.",
          used_for_answer: true,
        },
      ],
      error_message: "No aligned historical answer was found for this wording.",
      extensions: {
        retrieval_strategy: "semantic",
      },
    },
  ],
  summary: {
    total_questions_processed: 2,
    flagged_high_risk_or_inconsistent_responses: 1,
    overall_completion_status: "completed_with_warnings",
    completed_questions: 1,
    unanswered_questions: 1,
    failed_questions: 1,
    conflict_count: 0,
  },
};

const partialAndUnansweredTenderResponse = {
  request_id: "req-tender-124",
  session_id: "session-124",
  source_file_name: "tender.csv",
  total_questions_processed: 2,
  questions: [
    {
      question_id: "q-010",
      original_question: "Provide your FedRAMP package identifier.",
      generated_answer: null,
      domain_tag: "compliance",
      confidence_level: null,
      confidence_reason: null,
      historical_alignment_indicator: false,
      status: "unanswered",
      grounding_status: "no_reference",
      flags: {
        high_risk: false,
        inconsistent_response: false,
        has_conflict: false,
      },
      risk: {
        level: "low",
        reason: "No grounded answer was produced.",
      },
      metadata: {
        source_row_index: 0,
        alignment_record_id: null,
        alignment_score: null,
      },
      references: [],
      error_message: null,
      extensions: {},
    },
    {
      question_id: "q-011",
      original_question: "Describe your sovereign hosting guarantees.",
      generated_answer:
        "We support regional hosting controls (jurisdiction-specific sovereign hosting guarantees are not evidenced in the retrieved references).",
      domain_tag: "compliance",
      confidence_level: "medium",
      confidence_reason:
        "Confidence is reduced because the retrieved references support regional hosting controls but do not evidence jurisdiction-specific sovereign hosting guarantees or contractual commitments.",
      historical_alignment_indicator: true,
      status: "completed",
      grounding_status: "partial_reference",
      flags: {
        high_risk: false,
        inconsistent_response: false,
        has_conflict: true,
      },
      risk: {
        level: "medium",
        reason: "Human review is required before making hosting commitments.",
      },
      metadata: {
        source_row_index: 1,
        alignment_record_id: "qa-011",
        alignment_score: 0.68,
      },
      references: [
        {
          alignment_record_id: "qa-011",
          alignment_score: 0.68,
          source_doc: "compliance-history.csv",
          matched_question: "Describe your hosting controls.",
          matched_answer: "Regional hosting controls are available by deployment.",
          used_for_answer: true,
        },
      ],
      error_message: null,
      extensions: {
        conflicts: [
          {
            conflicting_question_id: "q-099",
            conflicting_question: "Do you support sovereign hosting guarantees?",
            reason:
              "This answer conflicts with a prior session answer that denied sovereign hosting guarantees.",
            severity: "high",
          },
        ],
      },
    },
  ],
  summary: {
    total_questions_processed: 2,
    flagged_high_risk_or_inconsistent_responses: 0,
    overall_completion_status: "completed",
    completed_questions: 1,
    unanswered_questions: 1,
    failed_questions: 0,
    conflict_count: 1,
  },
};

const documentReferenceTenderResponse = {
  request_id: "req-tender-125",
  session_id: "session-125",
  source_file_name: "tender.csv",
  total_questions_processed: 1,
  questions: [
    {
      question_id: "q-020",
      original_question: "How often do you test disaster recovery?",
      generated_answer: "Recovery exercises are run quarterly.",
      domain_tag: "operations",
      confidence_level: "medium",
      confidence_reason:
        "The answer is grounded by the retrieved operations excerpt.",
      historical_alignment_indicator: true,
      status: "completed",
      grounding_status: "grounded",
      flags: {
        high_risk: false,
        inconsistent_response: false,
        has_conflict: false,
      },
      risk: {
        level: "low",
        reason: "Low risk.",
      },
      metadata: {
        source_row_index: 0,
        alignment_record_id: "doc-1#0",
        alignment_score: 0.87,
      },
      references: [
        {
          alignment_record_id: "doc-1#0",
          reference_type: "document_chunk",
          alignment_score: 0.87,
          source_doc: "operations_playbook.txt",
          matched_question: "",
          matched_answer: "",
          excerpt: "Quarterly recovery exercises are documented and reviewed.",
          chunk_index: 0,
          used_for_answer: true,
        },
      ],
      error_message: null,
      extensions: {},
    },
  ],
  summary: {
    total_questions_processed: 1,
    flagged_high_risk_or_inconsistent_responses: 0,
    overall_completion_status: "completed",
    completed_questions: 1,
    unanswered_questions: 0,
    failed_questions: 0,
    conflict_count: 0,
  },
};

const failedIngestResponse = {
  request_id: "req-999",
  total_file_count: 2,
  processed_file_count: 1,
  failed_file_count: 1,
  request_options: {
    output_format: "json",
    similarity_threshold: 0.72,
  },
  files: [
    {
      status: "processed",
      payload: {
        file_name: "history-a.json",
        extension: ".json",
        content_type: "application/json",
        size_bytes: 12,
        parsed_kind: "json",
        raw_text: "{\"a\":1}",
        structured_data: { a: 1 },
        row_count: 1,
        warnings: [],
      },
      error_code: null,
      error_message: null,
      detected_columns: {
        question_col: "question",
        answer_col: "answer",
        domain_col: "domain",
      },
      ingested_row_count: 1,
      failed_row_count: 0,
      storage_target: "lancedb://qa_records",
    },
    {
      status: "failed",
      payload: {
        file_name: "pricing.csv",
        extension: ".csv",
        content_type: "text/csv",
        size_bytes: 32,
        parsed_kind: "csv",
        raw_text: "question,answer\nPricing,\n",
        structured_data: [],
        row_count: 1,
        warnings: ["Missing answer values"],
      },
      error_code: "missing_required_columns",
      error_message: "Could not identify the answer column.",
      detected_columns: {
        question_col: "question",
        answer_col: null,
        domain_col: null,
      },
      ingested_row_count: 0,
      failed_row_count: 1,
      storage_target: "lancedb://qa_records",
    },
  ],
};

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);

        if (url.endsWith("/api/health")) {
          return {
            ok: true,
            json: async () => mockHealthResponse,
          };
        }

        if (url.endsWith("/api/ingest/history") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => successfulIngestResponse,
          };
        }

        if (url.endsWith("/api/tender/respond") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => successfulTenderResponse,
          };
        }

        throw new Error(`Unhandled fetch for ${url}`);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  test("renders repository and response tabs and starts on the repository workspace", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /Tender Response Automation/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /Tender Repository/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /Tender Response/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Build knowledge base/i }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/Upload tender workbook/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Backend health: ok/i)).not.toBeInTheDocument();
  });

  test("renders autofill results inside the tender response tab after a csv upload", async () => {
    const user = userEvent.setup();

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Tender Response/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: /Tender Response/i }));

    const input = screen.getByLabelText(/Upload tender workbook/i);
    const file = new File(["question\nTLS"], "transport-tender.csv", {
      type: "text/csv",
    });

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /Autofill Tender/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/2 questions analyzed for transport-tender\.csv\./i),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/Do you support TLS 1\.2 or above\?/i)).toBeInTheDocument();
    expect(
      screen.getByText(/The platform enforces TLS 1\.2\+/i),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Completed With Warnings/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Workflow duration/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Workflow duration: \d+\.\d{2}s/i)).toBeInTheDocument();
    expect(screen.getByText(/Questions without a generated answer yet\./i)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Question/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Generated answer/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: /Domain/i }),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: /Open details for Describe your data residency controls\./i,
      }),
    );

    const dialog = screen.getByRole("dialog", { name: /Autofill details/i });

    expect(dialog).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");
    expect(screen.getByText(/No aligned historical answer was found/i)).toBeInTheDocument();
    expect(screen.queryByText(/Confidence/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        /There is some related historical material, but the wording is broader/i,
      ),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Risk review/i)).toBeInTheDocument();
    expect(
      screen.getByText(/could overstate contractual hosting guarantees/i),
    ).toBeInTheDocument();
    expect(within(dialog).getAllByText(/^High$/i)[0].className).toContain(
      "status-badge--danger",
    );
    expect(screen.getByText(/Reference matches/i)).toBeInTheDocument();
    expect(screen.getByText(/Partially Grounded/i)).toBeInTheDocument();
    expect(screen.getByText(/Alignment score:/i)).toBeInTheDocument();
    expect(screen.getByText("0.41")).toBeInTheDocument();
    expect(screen.getByText(/compliance-history\.csv/i)).toBeInTheDocument();
    expect(screen.getByText(/regional-controls\.csv/i)).toBeInTheDocument();
    expect(screen.getByText(/Describe data residency controls\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/Regional hosting is available with contract-specific controls\./i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Regional controls are available by deployment profile\./i)).toBeInTheDocument();
    expect(screen.getAllByText(/Used For Answer/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/alignment record/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/source row/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Close details/i }));

    expect(
      screen.queryByRole("dialog", { name: /Autofill details/i }),
    ).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
    expect(screen.queryByText(/Backend health: ok/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Unanswered questions: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Workflow duration: \d+\.\d{2}s/i)).toBeInTheDocument();
  });

  test("does not render confidence ui for unanswered questions", async () => {
    const user = userEvent.setup();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);

        if (url.endsWith("/api/health")) {
          return {
            ok: true,
            json: async () => mockHealthResponse,
          };
        }

        if (url.endsWith("/api/tender/respond") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => partialAndUnansweredTenderResponse,
          };
        }

        if (url.endsWith("/api/ingest/history") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => successfulIngestResponse,
          };
        }

        throw new Error(`Unhandled fetch for ${url}`);
      }),
    );

    render(<App />);

    await user.click(screen.getByRole("tab", { name: /Tender Response/i }));

    const input = screen.getByLabelText(/Upload tender workbook/i);
    const file = new File(["question\nFedRAMP"], "tender.csv", { type: "text/csv" });

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /Autofill Tender/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/2 questions analyzed for tender\.csv\./i),
      ).toBeInTheDocument();
    });

    const unansweredRow = screen
      .getByText(/Provide your FedRAMP package identifier\./i)
      .closest("tr");

    expect(unansweredRow).not.toBeNull();
    expect(within(unansweredRow!).queryByText(/^Low$/i)).not.toBeInTheDocument();
    expect(within(unansweredRow!).queryByText(/^Medium$/i)).not.toBeInTheDocument();
    expect(within(unansweredRow!).queryByText(/^High$/i)).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: /Open details for Provide your FedRAMP package identifier\./i,
      }),
    );

    const dialog = screen.getByRole("dialog", { name: /Autofill details/i });

    expect(
      within(dialog).queryByRole("heading", { name: /^Confidence$/i }),
    ).not.toBeInTheDocument();
  });

  test("keeps confidence ui for partial answers", async () => {
    const user = userEvent.setup();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);

        if (url.endsWith("/api/health")) {
          return {
            ok: true,
            json: async () => mockHealthResponse,
          };
        }

        if (url.endsWith("/api/tender/respond") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => partialAndUnansweredTenderResponse,
          };
        }

        if (url.endsWith("/api/ingest/history") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => successfulIngestResponse,
          };
        }

        throw new Error(`Unhandled fetch for ${url}`);
      }),
    );

    render(<App />);

    await user.click(screen.getByRole("tab", { name: /Tender Response/i }));

    const input = screen.getByLabelText(/Upload tender workbook/i);
    const file = new File(["question\nHosting"], "tender.csv", { type: "text/csv" });

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /Autofill Tender/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/2 questions analyzed for tender\.csv\./i),
      ).toBeInTheDocument();
    });

    const partialRow = screen
      .getByText(/Describe your sovereign hosting guarantees\./i)
      .closest("tr");

    expect(partialRow).not.toBeNull();
    expect(within(partialRow!).getByText(/^Medium$/i)).toBeInTheDocument();
    expect(within(partialRow!).getByText(/completed/i)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: /Open details for Describe your sovereign hosting guarantees\./i,
      }),
    );

    const dialog = screen.getByRole("dialog", { name: /Autofill details/i });

    expect(within(dialog).getByRole("heading", { name: /^Confidence$/i })).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        /Confidence is reduced because the retrieved references support regional hosting controls/i,
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/Partial Reference/i)).toBeInTheDocument();
  });

  test("renders document chunk references with excerpt-focused cards", async () => {
    const user = userEvent.setup();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);

        if (url.endsWith("/api/health")) {
          return {
            ok: true,
            json: async () => mockHealthResponse,
          };
        }

        if (url.endsWith("/api/tender/respond") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => documentReferenceTenderResponse,
          };
        }

        if (url.endsWith("/api/ingest/history") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => successfulIngestResponse,
          };
        }

        throw new Error(`Unhandled fetch for ${url}`);
      }),
    );

    render(<App />);

    await user.click(screen.getByRole("tab", { name: /Tender Response/i }));

    const input = screen.getByLabelText(/Upload tender workbook/i);
    const file = new File(["question\nDR"], "tender.csv", { type: "text/csv" });

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /Autofill Tender/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/1 questions analyzed for tender\.csv\./i),
      ).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", {
        name: /Open details for How often do you test disaster recovery\?/i,
      }),
    );

    const dialog = screen.getByRole("dialog", { name: /Autofill details/i });

    expect(
      within(dialog).getAllByText(/operations_playbook\.txt/i).length,
    ).toBeGreaterThan(0);
    expect(within(dialog).getByText(/Document Excerpt/i)).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        /Quarterly recovery exercises are documented and reviewed\./i,
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/Chunk 1/i)).toBeInTheDocument();
    expect(
      within(dialog).queryByText(/No matched question available\./i),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).queryByText(/No matched answer available\./i),
    ).not.toBeInTheDocument();
  });

  test("surfaces conflict status and conflict details for flagged answers", async () => {
    const user = userEvent.setup();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);

        if (url.endsWith("/api/health")) {
          return {
            ok: true,
            json: async () => mockHealthResponse,
          };
        }

        if (url.endsWith("/api/tender/respond") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => partialAndUnansweredTenderResponse,
          };
        }

        if (url.endsWith("/api/ingest/history") && init?.method === "POST") {
          return {
            ok: true,
            json: async () => successfulIngestResponse,
          };
        }

        throw new Error(`Unhandled fetch for ${url}`);
      }),
    );

    render(<App />);

    await user.click(screen.getByRole("tab", { name: /Tender Response/i }));

    const input = screen.getByLabelText(/Upload tender workbook/i);
    const file = new File(["question\nHosting"], "tender.csv", { type: "text/csv" });

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /Autofill Tender/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/2 questions analyzed for tender\.csv\./i),
      ).toBeInTheDocument();
    });

    expect(screen.getAllByText(/^Conflict$/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Conflict questions: 1/i)).toBeInTheDocument();

    const conflictRow = screen
      .getByText(/Describe your sovereign hosting guarantees\./i)
      .closest("tr");

    expect(conflictRow).not.toBeNull();
    expect(conflictRow?.className).toContain("result-row--conflict");
    expect(within(conflictRow!).getByText(/^Conflict$/i)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: /Open details for Describe your sovereign hosting guarantees\./i,
      }),
    );

    const dialog = screen.getByRole("dialog", { name: /Autofill details/i });

    expect(within(dialog).getByText(/^Conflict$/i)).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: /Conflict review/i })).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        /prior session answer that denied sovereign hosting guarantees/i,
      ),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Do you support sovereign hosting guarantees\?/i),
    ).toBeInTheDocument();
  });

  test("hides backend health while the service is healthy", async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Tender Repository/i })).toBeInTheDocument();
    });

    expect(screen.queryByText(/Backend health: ok/i)).not.toBeInTheDocument();
  });

  test("shows backend health only when the service is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "offline" }),
      }),
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Backend health: offline/i)).toBeInTheDocument();
    });
  });

  test("supports drag and drop uploads with a visible drop state", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getByRole("tab", { name: /Tender Response/i }));

    const dropzone = screen.getByLabelText(/Upload tender workbook/i).closest("div");

    expect(dropzone).not.toBeNull();

    fireEvent.dragEnter(dropzone!);

    expect(screen.getByText(/Drop workbook to queue this run/i)).toBeInTheDocument();

    const file = new File(["question\nTLS"], "dragged-tender.csv", {
      type: "text/csv",
    });

    fireEvent.drop(dropzone!, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(screen.getByText(/Selected file: dragged-tender\.csv/i)).toBeInTheDocument();
  });

  test("accepts xlsx uploads in the tender response tab", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getByRole("tab", { name: /Tender Response/i }));

    const input = screen.getByLabelText(/Upload tender workbook/i);
    const file = new File(["fake workbook"], "transport-tender.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await user.upload(input, file);

    expect(screen.getByText(/Selected file: transport-tender\.xlsx/i)).toBeInTheDocument();
    expect(screen.queryByText(/Autofill only accepts \.csv files\./i)).not.toBeInTheDocument();
  });

  test("uses custom upload controls instead of default form widgets", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(screen.getByRole("tab", { name: /Tender Response/i }));

    expect(screen.queryByRole("combobox", { name: /Output format/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("spinbutton", { name: /Similarity threshold/i })).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /Browse files/i }),
    ).toBeInTheDocument();

    expect(screen.getByText(/0.50/i)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /Increase alignment threshold/i }),
    );

    expect(screen.getByText(/0.51/i)).toBeInTheDocument();
  });

  test("uploads multiple knowledge files through the standalone ingest module", async () => {
    const user = userEvent.setup();

    render(<App />);

    const input = screen.getByLabelText(/Upload knowledge base files/i);
    const files = [
      new File(['{"domain":"security"}'], "security.json", {
        type: "application/json",
      }),
      new File(["# Architecture"], "architecture.md", {
        type: "text/markdown",
      }),
    ];

    await user.upload(input, files);
    expect(
      screen.getByRole("heading", { name: /Files queued for sync/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("security.json")).toBeInTheDocument();
    expect(screen.getByText("architecture.md")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Ingest Knowledge Files/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Knowledge base sync complete: 2 processed, 0 failed\./i),
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Select multiple files to preview the batch before sending it\./i),
    ).toBeInTheDocument();
    expect(screen.getByText(/history-a\.json/i)).toBeInTheDocument();
    expect(screen.getByText(/history-b\.md/i)).toBeInTheDocument();
  });

  test("accepts xlsx uploads in the knowledge base repository tab", async () => {
    const user = userEvent.setup();

    render(<App />);

    const input = screen.getByLabelText(/Upload knowledge base files/i);
    const files = [
      new File(["fake workbook"], "historical-library.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
    ];

    await user.upload(input, files);

    expect(screen.getByText("historical-library.xlsx")).toBeInTheDocument();
    expect(
      screen.getByText(/1 files staged for knowledge base ingest\./i),
    ).toBeInTheDocument();
  });

  test("accepts txt uploads in the knowledge base repository tab and advertises the full support list", async () => {
    const user = userEvent.setup();

    render(<App />);

    expect(
      screen.getByText(/Supports \.json, \.md, \.txt, \.csv, and \.xlsx/i),
    ).toBeInTheDocument();

    const input = screen.getByLabelText(/Upload knowledge base files/i);
    const files = [
      new File(["Escalate incidents within 30 minutes."], "operations.txt", {
        type: "text/plain",
      }),
    ];

    await user.upload(input, files);

    expect(screen.getByText("operations.txt")).toBeInTheDocument();
    expect(
      screen.getByText(/1 files staged for knowledge base ingest\./i),
    ).toBeInTheDocument();
  });

  test("appends newly added knowledge files to the queued batch before ingest", async () => {
    const user = userEvent.setup();

    render(<App />);

    const input = screen.getByLabelText(/Upload knowledge base files/i);
    const firstBatch = [
      new File(['{"domain":"security"}'], "security.json", {
        type: "application/json",
      }),
      new File(["# Architecture"], "architecture.md", {
        type: "text/markdown",
      }),
    ];
    const secondBatch = [
      new File(["question,domain\nPricing,Commercial"], "pricing.csv", {
        type: "text/csv",
      }),
    ];

    await user.upload(input, firstBatch);
    await user.upload(input, secondBatch);

    expect(screen.getByText("security.json")).toBeInTheDocument();
    expect(screen.getByText("architecture.md")).toBeInTheDocument();
    expect(screen.getAllByText("pricing.csv").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/3 files staged for knowledge base ingest\./i),
    ).toBeInTheDocument();
  });

  test("allows removing a queued knowledge file before ingest", async () => {
    const user = userEvent.setup();

    render(<App />);

    const input = screen.getByLabelText(/Upload knowledge base files/i);
    const files = [
      new File(['{"domain":"security"}'], "security.json", {
        type: "application/json",
      }),
      new File(["# Architecture"], "architecture.md", {
        type: "text/markdown",
      }),
    ];

    await user.upload(input, files);
    await user.click(
      screen.getByRole("button", { name: /Remove security\.json from queue/i }),
    );

    expect(screen.queryByText("security.json")).not.toBeInTheDocument();
    expect(screen.getByText("architecture.md")).toBeInTheDocument();
    expect(
      screen.getByText(/1 files staged for knowledge base ingest\./i),
    ).toBeInTheDocument();
  });

  test("shows file-level ingest failures and keeps the queue when the batch is not fully successful", async () => {
    const user = userEvent.setup();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);

        if (url.endsWith("/api/health")) {
          return { ok: true, json: async () => mockHealthResponse };
        }

        if (url.endsWith("/api/ingest/history") && init?.method === "POST") {
          return { ok: true, json: async () => failedIngestResponse };
        }

        throw new Error(`Unhandled fetch for ${url}`);
      }),
    );

    render(<App />);

    const input = screen.getByLabelText(/Upload knowledge base files/i);
    const files = [
      new File(['{"domain":"security"}'], "security.json", {
        type: "application/json",
      }),
      new File(["question,answer\nPricing,\n"], "pricing.csv", {
        type: "text/csv",
      }),
    ];

    await user.upload(input, files);
    await user.click(screen.getByRole("button", { name: /Ingest Knowledge Files/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Knowledge base sync complete: 1 processed, 1 failed\./i),
      ).toBeInTheDocument();
    });

    expect(screen.getAllByText("pricing.csv").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Could not identify the answer column\./i),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 failed rows/i)).toBeInTheDocument();
    expect(
      screen.getAllByText(/Target: lancedb:\/\/qa_records/i).length,
    ).toBeGreaterThan(0);
  });

  test("switches between repository and response workspaces without mixing the content", async () => {
    const user = userEvent.setup();

    render(<App />);

    const tablist = screen.getByRole("tablist", { name: /Workspace modules/i });
    const repositoryTab = within(tablist).getByRole("tab", {
      name: /Tender Repository/i,
    });
    const responseTab = within(tablist).getByRole("tab", {
      name: /Tender Response/i,
    });

    expect(repositoryTab).toHaveAttribute("aria-selected", "true");
    expect(responseTab).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("heading", { name: /Build knowledge base/i })).toBeInTheDocument();

    await user.click(responseTab);

    expect(repositoryTab).toHaveAttribute("aria-selected", "false");
    expect(responseTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: /Tender response/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Build knowledge base/i })).not.toBeInTheDocument();
  });
});
