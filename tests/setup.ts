import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { vi, afterEach } from "vitest";

// Clear DOM after each test to prevent pollution
afterEach(() => {
  cleanup();
});

class MockEventSource {
  onmessage: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  close = vi.fn();
  constructor(_url: string) {}
}

vi.stubGlobal("EventSource", MockEventSource);
