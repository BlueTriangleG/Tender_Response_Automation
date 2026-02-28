import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const mockHealthResponse = {
  status: "ok",
};

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockHealthResponse,
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
    expect(screen.getByLabelText(/Upload tender workbook/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Process Tender/i }),
    ).toBeInTheDocument();
  });

  test("renders health status and mock processing results after a file upload", async () => {
    const user = userEvent.setup();

    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText(/Backend health: ok/i)).toHaveLength(2);
    });

    const input = screen.getByLabelText(/Upload tender workbook/i);
    const file = new File(["sheet"], "transport-tender.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /Process Tender/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/3 questions analyzed for transport-tender.xlsx\./i),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/Submission readiness/i)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: /Expand result for Submission readiness/i,
      }),
    );

    expect(screen.getByText(/Generated answer/i)).toBeInTheDocument();
    expect(screen.getByText(/Historical matches/i)).toBeInTheDocument();
    expect(screen.getByText(/72%/i)).toBeInTheDocument();
  });

  test("supports drag and drop uploads with a visible drop state", async () => {
    render(<App />);

    const dropzone = screen.getByLabelText(/Upload tender workbook/i).closest("div");

    expect(dropzone).not.toBeNull();

    fireEvent.dragEnter(dropzone!);

    expect(screen.getByText(/Drop workbook to queue this run/i)).toBeInTheDocument();

    const file = new File(["sheet"], "dragged-tender.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    fireEvent.drop(dropzone!, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(screen.getByText(/Selected file: dragged-tender.xlsx/i)).toBeInTheDocument();
  });

  test("uses custom upload controls instead of default form widgets", async () => {
    const user = userEvent.setup();

    render(<App />);

    expect(screen.queryByRole("combobox", { name: /Output format/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("spinbutton", { name: /Similarity threshold/i })).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /Browse workbook/i }),
    ).toBeInTheDocument();
    const outputFormatGroup = screen.getByRole("group", { name: /Output format/i });

    expect(within(outputFormatGroup).getByRole("button", { name: /^JSON/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(
      within(outputFormatGroup).getByRole("button", { name: /^Excel/i }),
    );

    expect(
      within(outputFormatGroup).getByRole("button", { name: /^Excel/i }),
    ).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    expect(screen.getByText(/0.72/i)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /Increase similarity threshold/i }),
    );

    expect(screen.getByText(/0.73/i)).toBeInTheDocument();
  });
});
