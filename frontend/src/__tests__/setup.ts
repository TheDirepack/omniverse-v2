import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Clear DOM after each test to prevent pollution
afterEach(() => {
	cleanup();
});

// Mock scrollIntoView for JSDOM
HTMLElement.prototype.scrollIntoView = vi.fn();

class MockEventSource {
	onmessage: ((event: unknown) => void) | null = null;
	onerror: ((event: unknown) => void) | null = null;
	close = vi.fn();
}

vi.stubGlobal("EventSource", MockEventSource);
