import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TheoriesPanel from "../frontend/src/components/TheoriesPanel";
import * as api from "../frontend/src/api";

vi.mock("../frontend/src/api", () => ({
  fetchResults: vi.fn(),
  extrapolate: vi.fn(),
}));

describe("TheoriesPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads worlds via fetchResults on mount", async () => {
    vi.mocked(api.fetchResults).mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "Warhammer 40k", tier: 1, theory: "Chaos Gods are real", theory_audit: "Accepted", summary: null, tier_justification: null, is_explored: true },
        { id: 2, name: "Star Wars", tier: 3, theory: "The Force is a cosmic energy field", theory_audit: null, summary: null, tier_justification: null, is_explored: true },
      ],
      anomalies: [],
    });
    render(<TheoriesPanel />);
    await screen.findByText("Warhammer 40k");
    await screen.findByText("Star Wars");
    expect(api.fetchResults).toHaveBeenCalledOnce();
  });

  it("renders theory card with name, tier, theory, and auditor verdict", async () => {
    vi.mocked(api.fetchResults).mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "Warhammer 40k", tier: 2, theory: "Chaos Gods are real", theory_audit: "Accepted", summary: null, tier_justification: null, is_explored: true },
      ],
      anomalies: [],
    });
    render(<TheoriesPanel />);
    await screen.findByText("Warhammer 40k");
    expect(screen.getByText("Tier 2")).toBeInTheDocument();
    expect(screen.getByText(/Chaos Gods are real/)).toBeInTheDocument();
    expect(screen.getByText("Auditor Verdict")).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
  });

  it("shows empty state when no theories generated", async () => {
    vi.mocked(api.fetchResults).mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "Warhammer 40k", tier: 1, theory: null, theory_audit: null, summary: null, tier_justification: null, is_explored: true },
      ],
      anomalies: [],
    });
    render(<TheoriesPanel />);
    await screen.findByText("No theories generated yet. Use the trigger above to extrapolate interactions.");
  });

  it("filters out worlds without theory", async () => {
    vi.mocked(api.fetchResults).mockResolvedValue({
      tier_system: null,
      worlds: [
        { id: 1, name: "Has Theory", tier: 1, theory: "Something", theory_audit: null, summary: null, tier_justification: null, is_explored: true },
        { id: 2, name: "No Theory", tier: 2, theory: null, theory_audit: null, summary: null, tier_justification: null, is_explored: true },
      ],
      anomalies: [],
    });
    render(<TheoriesPanel />);
    await screen.findByText("Has Theory");
    expect(screen.queryByText("No Theory")).not.toBeInTheDocument();
  });

  it("handles fetchResults API error gracefully on mount", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(api.fetchResults).mockRejectedValue(new Error("Database offline"));
    
    render(<TheoriesPanel />);
    await waitFor(() => expect(api.fetchResults).toHaveBeenCalledOnce());
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it("triggers extrapolate API call with correct payload for 'all' scope", async () => {
    vi.mocked(api.fetchResults).mockResolvedValue({ tier_system: null, worlds: [], anomalies: [] });
    vi.mocked(api.extrapolate).mockResolvedValue({ run_id: "test-run", worlds: [] });
    
    render(<TheoriesPanel />);
    const button = await screen.findByText("Trigger Extrapolation");
    fireEvent.click(button);
    
    expect(api.extrapolate).toHaveBeenCalledWith({ scope: "all" });
  });

  it("triggers extrapolate API call with correct payload for 'worlds' scope", async () => {
    vi.mocked(api.fetchResults).mockResolvedValue({ tier_system: null, worlds: [], anomalies: [] });
    vi.mocked(api.extrapolate).mockResolvedValue({ run_id: "test-run", worlds: [] });
    
    render(<TheoriesPanel />);
    
    // Change scope to worlds
    const select = await screen.findByRole("combobox");
    fireEvent.change(select, { target: { value: "worlds" } });
    
    // Enter worlds
    const input = screen.getByPlaceholderText("Marvel, DC...");
    fireEvent.change(input, { target: { value: "Marvel, DC" } });
    
    const button = screen.getByText("Trigger Extrapolation");
    fireEvent.click(button);
    
    expect(api.extrapolate).toHaveBeenCalledWith({ 
      scope: "worlds", 
      worlds: ["Marvel", "DC"] 
    });
  });

  it("triggers extrapolate API call with correct payload for 'tier' scope", async () => {
    vi.mocked(api.fetchResults).mockResolvedValue({ tier_system: null, worlds: [], anomalies: [] });
    vi.mocked(api.extrapolate).mockResolvedValue({ run_id: "test-run", worlds: [] });
    
    render(<TheoriesPanel />);
    
    // Change scope to tier
    const select = await screen.findByRole("combobox");
    fireEvent.change(select, { target: { value: "tier" } });
    
    // Enter tier
    const input = screen.getByPlaceholderText("5");
    fireEvent.change(input, { target: { value: "5" } });
    
    const button = screen.getByText("Trigger Extrapolation");
    fireEvent.click(button);
    
    expect(api.extrapolate).toHaveBeenCalledWith({ 
      scope: "tier", 
      tier: 5 
    });
  });
});
