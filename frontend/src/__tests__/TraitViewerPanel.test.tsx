import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import TraitViewerPanel from "../components/TraitViewerPanel";

vi.mock("../api", () => ({
	fetchResults: vi.fn(),
	fetchTraits: vi.fn(),
	fetchClaims: vi.fn(),
}));

describe("TraitViewerPanel", () => {
	const mockWorlds = [
		{
			id: 1,
			name: "World A",
			summary: "Sum A",
			is_explored: true,
			tier: 1,
			tier_justification: "J1",
			theory: "T1",
			theory_audit: "A1",
		},
		{
			id: 2,
			name: "World B",
			summary: "Sum B",
			is_explored: true,
			tier: 2,
			tier_justification: "J2",
			theory: "T2",
			theory_audit: "A2",
		},
		{
			id: 3,
			name: "World C",
			summary: "Sum C",
			is_explored: true,
			tier: 3,
			tier_justification: "J3",
			theory: "T3",
			theory_audit: "A3",
		},
	];

	const mockTraits = [
		{
			id: 101,
			universe_id: 1,
			category: "Magic",
			name: "System",
			value: "Hard Magic",
		},
		{
			id: 102,
			universe_id: 1,
			category: "Magic",
			name: "Power",
			value: "High",
		},
		{
			id: 201,
			universe_id: 2,
			category: "Tech",
			name: "Level",
			value: "Intergalactic",
		},
		// World 3 has no traits
	];

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(api.fetchResults).mockResolvedValue({
			tier_system: "Test System",
			worlds: mockWorlds,
			anomalies: [],
		});
		vi.mocked(api.fetchTraits).mockResolvedValue(mockTraits);
		vi.mocked(api.fetchClaims).mockResolvedValue([]);
	});

	it("renders loading state initially", () => {
		// We need to prevent the immediate resolution of the promise for this test
		vi.mocked(api.fetchResults).mockReturnValue(new Promise(() => {}));
		render(<TraitViewerPanel />);
		expect(screen.getByText(/Loading database.../i)).toBeInTheDocument();
	});

	it("renders worlds and their traits correctly", async () => {
		render(<TraitViewerPanel />);

		await waitFor(() => {
			expect(screen.getByText("World A")).toBeInTheDocument();
			expect(screen.getByText("World B")).toBeInTheDocument();
			expect(screen.getByText("World C")).toBeInTheDocument();
		});

		expect(screen.getByText("System:")).toBeInTheDocument();
		expect(screen.getByText("Hard Magic")).toBeInTheDocument();
		expect(screen.getByText("Level:")).toBeInTheDocument();
		expect(screen.getByText("Intergalactic")).toBeInTheDocument();
	});

	it("filters worlds when 'Only worlds with traits' is checked", async () => {
		render(<TraitViewerPanel />);

		await waitFor(() => {
			expect(screen.getByText("World C")).toBeInTheDocument();
		});

		const checkbox = screen.getByLabelText(/Only worlds with data/i);
		fireEvent.click(checkbox);

		expect(screen.getByText("World A")).toBeInTheDocument();
		expect(screen.getByText("World B")).toBeInTheDocument();
		expect(screen.queryByText("World C")).not.toBeInTheDocument();
	});

	it("shows empty message when no worlds match filter", async () => {
		vi.mocked(api.fetchTraits).mockResolvedValue([]);

		render(<TraitViewerPanel />);

		await waitFor(() => {
			expect(screen.getByText("World A")).toBeInTheDocument();
		});

		const checkbox = screen.getByLabelText(/Only worlds with data/i);
		fireEvent.click(checkbox);

		expect(
			screen.getByText(/No worlds found matching the current filter/i),
		).toBeInTheDocument();
		expect(screen.queryByText("World A")).not.toBeInTheDocument();
	});
});
