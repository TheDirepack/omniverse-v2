import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DatabasePanel from "../frontend/src/components/DatabasePanel";

const mockFetchResults = vi.fn();

vi.mock("../frontend/src/api", () => ({
  fetchResults: mockFetchResults,
}));

describe("DatabasePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads data via fetchResults on mount", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: "A powerful entity is Tier 1, mundane is Tier 10.",
      worlds: [{ id: 1, name: "Warhammer 40k", tier: 1, summary: null, tier_justification: "Cosmic scale", is_explored: true, theory: null, theory_audit: null }],
      anomalies: [],
    });
    render(<DatabasePanel />);
    await screen.findByText("Tier 1");
    await screen.findByText("Warhammer 40k");
    expect(mockFetchResults).toHaveBeenCalledOnce();
  });

  it("renders tier system definition when present", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: "A powerful entity is Tier 1, mundane is Tier 10.",
      worlds: [],
      anomalies: [],
    });
    render(<DatabasePanel />);
    await screen.findByText("System Definition");
    expect(screen.getByText(/A powerful entity is Tier 1/)).toBeInTheDocument();
  });

  it("shows empty state when no tier system", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: null,
      worlds: [],
      anomalies: [],
    });
    render(<DatabasePanel />);
    await screen.findByText("No tier system yet. Run the pipeline to generate one.");
  });

  it("groups worlds by tier in ascending order", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "High Tier", tier: 1, summary: null, tier_justification: null, is_explored: true, theory: null, theory_audit: null },
        { id: 2, name: "Mid Tier", tier: 5, summary: null, tier_justification: null, is_explored: true, theory: null, theory_audit: null },
        { id: 3, name: "Low Tier", tier: 10, summary: null, tier_justification: null, is_explored: true, theory: null, theory_audit: null },
      ],
      anomalies: [],
    });
    render(<DatabasePanel />);

    const tierLabels = await screen.findAllByText(/Tier \d+/);
    expect(tierLabels).toHaveLength(3);
    expect(tierLabels[0].textContent).toBe("Tier 1");
    expect(tierLabels[1].textContent).toBe("Tier 5");
    expect(tierLabels[2].textContent).toBe("Tier 10");
  });

  it("shows world detail when world chip is clicked", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "Warhammer 40k", tier: 1, summary: null, tier_justification: "Galactic-scale conflict", is_explored: true, theory: null, theory_audit: null },
      ],
      anomalies: [],
    });
    const user = userEvent.setup();
    render(<DatabasePanel />);
    await screen.findByText("Warhammer 40k");

    await user.click(screen.getByText("Warhammer 40k"));
    expect(screen.getByText(/Galactic-scale conflict/)).toBeInTheDocument();
    expect(screen.getByText("Tier 1")).toBeInTheDocument();
  });

  it("shows anomalies in world detail when present", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "Warhammer 40k", tier: 1, summary: null, tier_justification: "test", is_explored: true, theory: null, theory_audit: null },
      ],
      anomalies: [
        { world_id: 1, description: "Temporal paradox detected", detected_at: "2024-01-01" },
      ],
    });
    const user = userEvent.setup();
    render(<DatabasePanel />);
    await screen.findByText("Warhammer 40k");
    await user.click(screen.getByText("Warhammer 40k"));
    expect(screen.getByText("Anomalies")).toBeInTheDocument();
    expect(screen.getByText("Temporal paradox detected")).toBeInTheDocument();
  });

  it("shows ontological theory and auditor feedback in detail", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "Warhammer 40k", tier: 1, summary: null, tier_justification: "test", is_explored: true, theory: "The Chaos Gods are multidimensional entities", theory_audit: "Plausible, needs more evidence" },
      ],
      anomalies: [],
    });
    const user = userEvent.setup();
    render(<DatabasePanel />);
    await screen.findByText("Warhammer 40k");
    await user.click(screen.getByText("Warhammer 40k"));
    expect(screen.getByText("Ontological Theory")).toBeInTheDocument();
    expect(screen.getByText(/The Chaos Gods are multidimensional/)).toBeInTheDocument();
    expect(screen.getByText("Auditor Feedback")).toBeInTheDocument();
    expect(screen.getByText(/Plausible, needs more/)).toBeInTheDocument();
  });

  it("shows global anomalies section", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: null,
      worlds: [],
      anomalies: [
        { world_id: null, description: "Universal constant shift", detected_at: "2024-01-01" },
      ],
    });
    render(<DatabasePanel />);
    await screen.findByText("Global Anomalies");
    expect(screen.getByText("Universal constant shift")).toBeInTheDocument();
  });

  it("shows selected chip as active", async () => {
    mockFetchResults.mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "Warhammer 40k", tier: 1, summary: null, tier_justification: null, is_explored: true, theory: null, theory_audit: null },
        { id: 2, name: "Star Wars", tier: 1, summary: null, tier_justification: null, is_explored: true, theory: null, theory_audit: null },
      ],
      anomalies: [],
    });
    const user = userEvent.setup();
    render(<DatabasePanel />);
    await screen.findByText("Warhammer 40k");

    await user.click(screen.getByText("Warhammer 40k"));
    expect(screen.getByText("Warhammer 40k").closest("button")).toHaveClass("active");
  });
});
