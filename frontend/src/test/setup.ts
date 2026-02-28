import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest does not guarantee automatic DOM cleanup in every setup path, so we
// register it explicitly to keep each test isolated.
afterEach(() => {
  cleanup();
});
