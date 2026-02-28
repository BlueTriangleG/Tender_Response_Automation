import { afterEach, describe, expect, test, vi } from "vitest";

import { ingestHistoryFiles, processTenderWorkbook } from "./api";

describe("ingestHistoryFiles", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  test("sends batch files to the history ingest api as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        request_id: "req-42",
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
              file_name: "alpha.json",
              extension: ".json",
              content_type: "application/json",
              size_bytes: 15,
              parsed_kind: "json",
              raw_text: "{\"ok\":true}",
              structured_data: { ok: true },
              row_count: 1,
              warnings: [],
            },
            error_code: null,
            error_message: null,
          },
        ],
      }),
    });

    vi.stubGlobal("fetch", fetchMock);

    const files = [
      new File(['{"ok":true}'], "alpha.json", { type: "application/json" }),
      new File(["# Notes"], "notes.md", { type: "text/markdown" }),
    ];

    const response = await ingestHistoryFiles(files);

    expect(response.totalFileCount).toBe(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];

    expect(url).toBe("http://127.0.0.1:8000/api/ingest/history");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);

    const formData = init.body as FormData;
    const uploadedFiles = formData.getAll("files");

    expect(uploadedFiles).toHaveLength(2);
    expect(uploadedFiles[0]).toBe(files[0]);
    expect(uploadedFiles[1]).toBe(files[1]);
    expect(formData.get("outputFormat")).toBe("json");
    expect(formData.get("similarityThreshold")).toBe("0.72");
  });
});

describe("processTenderWorkbook", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  test("sends the tender csv to the tender response api as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        request_id: "req-tender-42",
        session_id: "session-42",
        source_file_name: "tender.csv",
        total_questions_processed: 1,
        questions: [
          {
            question_id: "q-001",
            original_question: "Do you support TLS 1.2+?",
            generated_answer: "Yes.",
            domain_tag: "security",
            confidence_level: "high",
            confidence_reason: "The answer is directly supported by prior submissions.",
            historical_alignment_indicator: true,
            status: "completed",
            grounding_status: "grounded",
            flags: {
              high_risk: false,
              inconsistent_response: false,
            },
            metadata: {
              source_row_index: 0,
              alignment_record_id: "qa-001",
              alignment_score: 0.93,
            },
            risk: {
              level: "low",
              reason: "This is a standard capability with low delivery risk.",
            },
            references: [
              {
                alignment_record_id: "qa-001",
                alignment_score: 0.93,
                source_doc: "security-history.csv",
                matched_question: "Do you support TLS 1.2+?",
                matched_answer: "Yes.",
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
        },
      }),
    });

    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["question\nTLS"], "tender.csv", { type: "text/csv" });

    const response = await processTenderWorkbook(file, {
      alignmentThreshold: 0.84,
    });

    expect(response.sessionId).toBe("session-42");
    expect(response.questions[0].groundingStatus).toBe("grounded");
    expect(response.questions[0].confidenceReason).toBe(
      "The answer is directly supported by prior submissions.",
    );
    expect(response.questions[0].alignmentScore).toBe(0.93);
    expect(response.questions[0].risk).toEqual({
      level: "low",
      reason: "This is a standard capability with low delivery risk.",
    });
    expect(response.questions[0].references[0].sourceDoc).toBe("security-history.csv");
    expect(response.questions[0].references[0].usedForAnswer).toBe(true);
    expect(response.summary.unansweredQuestions).toBe(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];

    expect(url).toBe("http://127.0.0.1:8000/api/tender/respond");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);

    const formData = init.body as FormData;

    expect(formData.get("file")).toBe(file);
    expect(formData.get("alignmentThreshold")).toBe("0.84");
  });
});
