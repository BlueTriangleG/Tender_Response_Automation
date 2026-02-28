import { afterEach, describe, expect, test, vi } from "vitest";

import { ingestHistoryFiles } from "./api";

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
