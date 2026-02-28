import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      historical_alignment_indicator: true,
      status: "completed",
      flags: {
        high_risk: false,
        inconsistent_response: false,
      },
      metadata: {
        source_row_index: 0,
        alignment_record_id: "qa-001",
        alignment_score: 0.94,
      },
      error_message: null,
      extensions: {},
    },
    {
      question_id: "q-002",
      original_question: "Describe your data residency controls.",
      generated_answer: "",
      domain_tag: "compliance",
      confidence_level: "medium",
      historical_alignment_indicator: false,
      status: "failed",
      flags: {
        high_risk: true,
        inconsistent_response: true,
      },
      metadata: {
        source_row_index: 1,
        alignment_record_id: "qa-002",
        alignment_score: 0.41,
      },
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
    failed_questions: 1,
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

  test("renders the tender dashboard shell", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /Tender Response Automation/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/A structured batch-processing workspace for retrieval-backed tender answers/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Processing spotlight/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Upload tender csv/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Autofill Tender/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Build knowledge base/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Ingest Knowledge Files/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /Build knowledge base/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Upload tender csv/i }),
    ).toBeInTheDocument();
  });

  test("renders autofill results from the tender response api after a csv upload", async () => {
    const user = userEvent.setup();

    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText(/Backend health: ok/i)).toHaveLength(2);
    });

    const input = screen.getByLabelText(/Upload tender csv/i);
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
    expect(screen.getAllByText(/completed_with_warnings/i).length).toBeGreaterThan(0);

    await user.click(
      screen.getByRole("button", {
        name: /Expand result for Describe your data residency controls\./i,
      }),
    );

    expect(screen.getByText(/No aligned historical answer was found/i)).toBeInTheDocument();
    expect(screen.getByText(/alignment score/i)).toBeInTheDocument();
    expect(screen.getAllByText(/high risk/i).length).toBeGreaterThan(0);
  });

  test("keeps the health badge neutral while the backend check is still pending", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise(() => {
            // Intentionally unresolved to keep the dashboard in its initial
            // loading state so the health badge styling can be verified.
          }),
      ),
    );

    render(<App />);

    const healthBadges = screen.getAllByText(/Backend health: checking/i);

    expect(healthBadges).toHaveLength(2);

    for (const badge of healthBadges) {
      expect(badge).not.toHaveClass("status-badge--danger");
    }
  });

  test("normalizes the backend health status before rendering success state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "OK" }),
      }),
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText(/Backend health: ok/i)).toHaveLength(2);
    });
  });

  test("supports drag and drop uploads with a visible drop state", async () => {
    render(<App />);

    const dropzone = screen.getByLabelText(/Upload tender csv/i).closest("div");

    expect(dropzone).not.toBeNull();

    fireEvent.dragEnter(dropzone!);

    expect(screen.getByText(/Drop csv to queue this run/i)).toBeInTheDocument();

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

  test("uses custom upload controls instead of default form widgets", async () => {
    const user = userEvent.setup();

    render(<App />);

    expect(screen.queryByRole("combobox", { name: /Output format/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("spinbutton", { name: /Similarity threshold/i })).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /Browse csv/i }),
    ).toBeInTheDocument();

    expect(screen.getByText(/0.82/i)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /Increase alignment threshold/i }),
    );

    expect(screen.getByText(/0.83/i)).toBeInTheDocument();
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
});
