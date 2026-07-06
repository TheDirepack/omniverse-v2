import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import DatabasePanel from "../components/DatabasePanel";

vi.mock("../api", () => ({
	fetchWorlds: vi.fn(),
	fetchResults: vi.fn(),
	fetchTraits: vi.fn(),
	fetchClaims: vi.fn(),
	fetchUnconfirmedTraits: vi.fn(),
	fetchUnconfirmedClaims: vi.fn(),
	runTiering: vi.fn(),
	createEventSource: vi.fn(),
	startOrchestrate: vi.fn(),
	researchUnexplored: vi.fn(),
	addWorld: vi.fn(),
	resetAllExplored: vi.fn(),
	resetWorldExplored: vi.fn(),
	resetDatabase: vi.fn(),
	clearLogsApi: vi.fn(),
	abortRun: vi.fn(),
}));

const mockWorlds = [
	{
		id: 1,
		name: "World A",
		summary: "S1",
		is_explored: true,
		tier: 1,
		tier_justification: "J1",
		theory: "T1",
		theory_audit: "A1",
	},
	{
		id: 2,
		name: "World B",
		summary: "S2",
		is_explored: true,
		tier: 2,
		tier_justification: "J2",
		theory: "T2",
		theory_audit: "A2",
	},
];

const mockTraits = [
	{
		id: 1,
		universe_id: 1,
		category: "Cosmology",
		name: "Size",
		value: "Large",
	},
	{ id: 2, universe_id: 1, category: "Magic", name: "Type", value: "Arcane" },
	{
		id: 3,
		universe_id: 2,
		category: "Cosmology",
		name: "Size",
		value: "Medium",
	},
	{ id: 4, universe_id: 2, category: "Tech", name: "Level", value: "High" },
];

const mockResults = {
	tier_system: "Rubric v1",
	worlds: mockWorlds,
	anomalies: [],
};

describe("DatabasePanel", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(api.fetchWorlds).mockResolvedValue(mockWorlds);
		vi.mocked(api.fetchResults).mockResolvedValue(mockResults);
		vi.mocked(api.fetchTraits).mockResolvedValue(mockTraits);
		vi.mocked(api.fetchClaims).mockResolvedValue([]);
		vi.mocked(api.fetchUnconfirmedTraits).mockResolvedValue([]);
		vi.mocked(api.fetchUnconfirmedClaims).mockResolvedValue([]);
	});

	it("renders worlds and allows selecting one for details", async () => {
		render(<DatabasePanel />);

		await waitFor(() => {
			expect(screen.getByText("World A")).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole("button", { name: "World A" }));

		expect(
			screen.getByRole("heading", { name: "World A" }),
		).toBeInTheDocument();
		expect(screen.getByText("Tier 1")).toBeInTheDocument();
		expect(screen.getByText("J1")).toBeInTheDocument();
	});

	it("displays traits grouped by category in detail view", async () => {
		render(<DatabasePanel />);

		await waitFor(() => {
			expect(screen.getByText("World A")).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole("button", { name: "World A" }));

		expect(screen.getByText("Cosmology")).toBeInTheDocument();
		expect(screen.getByText("Magic")).toBeInTheDocument();
		expect(screen.getByText("Size")).toBeInTheDocument();
		expect(screen.getByText("Large")).toBeInTheDocument();
	});

	it("toggles comparison mode and renders the matrix", async () => {
		render(<DatabasePanel />);

		await waitFor(() => {
			expect(screen.getByText("World A")).toBeInTheDocument();
		});

		fireEvent.click(screen.getByText("Compare Worlds"));

		fireEvent.click(screen.getByRole("button", { name: "World A" }));
		fireEvent.click(screen.getByRole("button", { name: "World B" }));

		// Check if matrix headers are present
		expect(screen.getByText("Trait")).toBeInTheDocument();
		expect(
			screen.getByRole("columnheader", { name: "World A" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("columnheader", { name: "World B" }),
		).toBeInTheDocument();

		// Check if shared traits are present
		expect(screen.getByText("Size")).toBeInTheDocument();
		expect(screen.getByText("Large")).toBeInTheDocument();
		expect(screen.getByText("Medium")).toBeInTheDocument();

		// Check if unique traits are present
		expect(screen.getByText("Type")).toBeInTheDocument();
		expect(screen.getByText("Arcane")).toBeInTheDocument();
		expect(screen.getByText("N/A")).toBeInTheDocument();
	});

	it("returns to detail view when toggled", async () => {
		render(<DatabasePanel />);

		await waitFor(() => {
			expect(screen.getByText("World A")).toBeInTheDocument();
		});

		fireEvent.click(screen.getByText("Compare Worlds"));
		fireEvent.click(screen.getByText("View Details"));

		expect(screen.queryByText("Trait")).not.toBeInTheDocument();
	});
});
