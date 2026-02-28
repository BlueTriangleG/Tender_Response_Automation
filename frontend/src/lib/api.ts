import { mockHistoryStatus, mockTenderSession } from "./mockData";
import type {
  BackendHealth,
  HistoryStatus,
  ProcessOptions,
  TenderSession,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const wait = (duration: number) =>
  new Promise((resolve) => window.setTimeout(resolve, duration));

// Health is the only live backend contract available today, so the dashboard
// fetches it directly to prove that the frontend is wired to the real API.
export async function fetchBackendHealth(): Promise<BackendHealth> {
  const response = await fetch(`${API_BASE_URL}/api/health`);

  if (!response.ok) {
    throw new Error("Backend health request failed.");
  }

  return (await response.json()) as BackendHealth;
}

// The planning doc expects a history card, but the backend endpoint does not
// exist yet. Returning a stable mock keeps the UI demonstrable without hiding
// the dependency gap.
export async function fetchHistoryStatus(): Promise<HistoryStatus> {
  await wait(120);
  return mockHistoryStatus;
}

// The process flow is intentionally mocked for now. It mirrors the shape the
// backend is expected to return so the UI can be swapped to a real API later.
export async function processTenderWorkbook(
  file: File,
  _options: ProcessOptions,
): Promise<TenderSession> {
  await wait(240);

  return {
    ...mockTenderSession,
    fileName: file.name,
    sessionId: `${mockTenderSession.sessionId}-${file.name.replaceAll(/\W+/g, "-")}`,
  };
}
