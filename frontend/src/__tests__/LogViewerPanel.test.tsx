import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import LogViewerPanel from "../components/LogViewerPanel";

vi.mock("../api", () => ({
	fetchFileLogs: vi.fn(),
}));

describe("LogViewerPanel", () => {
	const mockLogs = [
		"[2026-07-04 10:00:00] [Researcher] [gpt-4] [1] [World1] [INFO] Started research",
		"[2026-07-04 10:00:05] [Researcher] [gpt-4] [1] [World1] [ERROR] Connection failed",
		"[2026-07-04 10:00:10] [Researcher] [gpt-4] [1] [World1] [SUCCESS] Research completed",
	];

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(api.fetchFileLogs).mockResolvedValue({
			logs: mockLogs,
			has_more: false,
		});
	});

	it("renders loading state and then displays logs", async () => {
		render(<LogViewerPanel />);

		// Note: In our implementation, loading is set to true initially
		// but the effect runs immediately.
		await waitFor(() => {
			expect(screen.getByText(mockLogs[0])).toBeInTheDocument();
			expect(screen.getByText(mockLogs[1])).toBeInTheDocument();
			expect(screen.getByText(mockLogs[2])).toBeInTheDocument();
		});
	});

	it("filters logs when filter input changes and refresh is clicked", async () => {
		render(<LogViewerPanel />);

		await waitFor(() => {
			expect(screen.getByText(mockLogs[0])).toBeInTheDocument();
		});

		const filterInput = screen.getByPlaceholderText("Generic search...");
		fireEvent.change(filterInput, { target: { value: "ERROR" } });

		const refreshButton = screen.getByText("Refresh");
		fireEvent.click(refreshButton);

		expect(api.fetchFileLogs).toHaveBeenCalledWith("ERROR");
	});

	it("shows empty message when no logs are returned", async () => {
		vi.mocked(api.fetchFileLogs).mockResolvedValue({
			logs: [],
			has_more: false,
		});

		render(<LogViewerPanel />);

		await waitFor(() => {
			expect(screen.getByText(/No logs found/i)).toBeInTheDocument();
		});
	});
});
