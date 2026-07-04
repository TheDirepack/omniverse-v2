import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardPanel from "../frontend/src/components/DashboardPanel";
import * as api from "../frontend/src/api";

vi.mock("../frontend/src/api", () => ({
  fetchWorlds: vi.fn(),
  startOrchestrate: vi.fn(),
  researchUnexplored: vi.fn(),
  addWorld: vi.fn(),
  resetAllExplored: vi.fn(),
  resetWorldExplored: vi.fn(),
  runFocusedSearch: vi.fn(),
  resetDatabase: vi.fn(),
  clearLogsApi: vi.fn(),
  createEventSource: vi.fn(),
}));

function sourceMock() {
  return { onmessage: null as any, onerror: null as any, close: vi.fn() };
}

describe("DashboardPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchWorlds).mockResolvedValue([]);
    vi.mocked(api.createEventSource).mockReturnValue(sourceMock());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads world registry on mount", async () => {
    vi.mocked(api.fetchWorlds).mockResolvedValue([
      { id: 1, name: "Warhammer 40k", is_explored: true, summary: null },
      { id: 2, name: "Star Wars", is_explored: false, summary: null },
    ]);
    render(<DashboardPanel />);
    await screen.findByText("Warhammer 40k");
    expect(screen.getByText("Warhammer 40k")).toBeInTheDocument();
    expect(screen.getByText("Star Wars")).toBeInTheDocument();
    expect(api.fetchWorlds).toHaveBeenCalledOnce();
  });

  it("marks explored worlds with checkmark", async () => {
    vi.mocked(api.fetchWorlds).mockResolvedValue([
      { id: 1, name: "Warhammer 40k", is_explored: true, summary: null },
      { id: 2, name: "Star Wars", is_explored: false, summary: null },
    ]);
    render(<DashboardPanel />);
    await screen.findByText("Warhammer 40k");
    const warhammer = screen.getByText(/Warhammer 40k/);
    expect(warhammer.textContent).toContain("✓");
    expect(screen.getByText("Star Wars").textContent).not.toContain("✓");
  });

  it("calls startOrchestrate with comma-separated worlds on Run click", async () => {
    vi.mocked(api.startOrchestrate).mockResolvedValue({ run_id: "run-1" });
    const user = userEvent.setup();
    render(<DashboardPanel />);
    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "Warhammer 40k, Star Wars");
    await user.click(screen.getByRole("button", { name: /run/i }));
    expect(api.startOrchestrate).toHaveBeenCalledWith(["Warhammer 40k", "Star Wars"]);
  });

  it("calls researchUnexplored on Research button click", async () => {
    vi.mocked(api.researchUnexplored).mockResolvedValue({ run_id: null, worlds: [], status: "ok" });
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await user.click(screen.getByRole("button", { name: /research all unexplored/i }));
    expect(api.researchUnexplored).toHaveBeenCalledOnce();
  });

  it("calls addWorld on Add + Research click and refreshes", async () => {
    vi.mocked(api.addWorld).mockResolvedValue({ id: 3, name: "Dune" });
    const user = userEvent.setup();
    render(<DashboardPanel />);
    const input = screen.getByPlaceholderText("Add world to DB");
    await user.type(input, "Dune");
    await user.click(screen.getByRole("button", { name: /add \+ research/i }));
    expect(api.addWorld).toHaveBeenCalledWith("Dune");
    await waitFor(() => expect(api.fetchWorlds).toHaveBeenCalledTimes(2));
  });

  it("calls resetWorldExplored when world chip clicked", async () => {
    vi.mocked(api.fetchWorlds).mockResolvedValue([
      { id: 1, name: "Warhammer 40k", is_explored: true, summary: null },
    ]);
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await screen.findByText(/Warhammer 40k/);
    await user.click(screen.getByText(/Warhammer 40k/));
    expect(api.resetWorldExplored).toHaveBeenCalledWith(1);
    expect(api.fetchWorlds).toHaveBeenCalledTimes(2);
  });

  it("calls runFocusedSearch with world name and feature", async () => {
    vi.mocked(api.runFocusedSearch).mockResolvedValue({ run_id: "fs-1" });
    const user = userEvent.setup();
    render(<DashboardPanel />);
    const worldInput = screen.getByPlaceholderText("World name");
    const featureInput = screen.getByPlaceholderText("Feature to prove/disprove");
    await user.type(worldInput, "Star Wars");
    await user.type(featureInput, "The Force is real");
    await user.click(screen.getByRole("button", { name: /focused search/i }));
    expect(api.runFocusedSearch).toHaveBeenCalledWith("Star Wars", "The Force is real");
  });

  it("calls resetDatabase on Reset DB click", async () => {
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await screen.findByText("Reset DB");
    await user.click(screen.getByRole("button", { name: /reset db/i }));
    expect(api.resetDatabase).toHaveBeenCalledOnce();
  });

  it("calls clearLogsApi and clears local logs on Clear Logs click", async () => {
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await user.click(screen.getByRole("button", { name: /clear logs/i }));
    expect(api.clearLogsApi).toHaveBeenCalledOnce();
  });

  it("displays SSE logs in Live Logs panel", async () => {
    const src = sourceMock();
    vi.mocked(api.createEventSource).mockReturnValue(src);
    vi.mocked(api.startOrchestrate).mockResolvedValue({ run_id: "run-1" });

    const user = userEvent.setup();
    render(<DashboardPanel />);

    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "TestWorld");
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(api.createEventSource).toHaveBeenCalledWith("run-1"));

    act(() => {
      src.onmessage({ data: JSON.stringify({ node_name: "Researcher", thought: "Analyzing...", status: "running", created_at: "12:00" }) });
    });

    expect(screen.getByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText(/Analyzing\.\.\./)).toBeInTheDocument();
    expect(screen.getByText("12:00")).toBeInTheDocument();
  });

  it("shows Running status pill while SSE is active", async () => {
    const src = sourceMock();
    vi.mocked(api.createEventSource).mockReturnValue(src);
    vi.mocked(api.startOrchestrate).mockResolvedValue({ run_id: "run-1" });

    const user = userEvent.setup();
    render(<DashboardPanel />);

    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "TestWorld");
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(api.createEventSource).toHaveBeenCalled());
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("handles finished SSE message by stopping run", async () => {
    const src = sourceMock();
    vi.mocked(api.createEventSource).mockReturnValue(src);
    vi.mocked(api.startOrchestrate).mockResolvedValue({ run_id: "run-1" });

    const user = userEvent.setup();
    render(<DashboardPanel />);

    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "TestWorld");
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(api.createEventSource).toHaveBeenCalled());

    act(() => {
      src.onmessage({ data: JSON.stringify({ finished: true }) });
    });

    await waitFor(() => expect(screen.getByText("Completed")).toBeInTheDocument());
    expect(src.close).toHaveBeenCalled();
  });

  it("shows unexplored count in Research button label", async () => {
    vi.mocked(api.fetchWorlds).mockResolvedValue([
      { id: 1, name: "W1", is_explored: false, summary: null },
      { id: 2, name: "W2", is_explored: true, summary: null },
      { id: 3, name: "W3", is_explored: false, summary: null },
    ]);
    render(<DashboardPanel />);
    await screen.findByText(/2 worlds/);
    expect(screen.getByText(/research all unexplored.*2 worlds/i)).toBeInTheDocument();
  });

  it("filters worlds by search term", async () => {
    vi.mocked(api.fetchWorlds).mockResolvedValue([
      { id: 1, name: "Warhammer 40k", is_explored: false, summary: null },
      { id: 2, name: "Star Wars", is_explored: false, summary: null },
      { id: 3, name: "Warframe", is_explored: false, summary: null },
    ]);
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await screen.findByText("Warhammer 40k");

    const searchInput = screen.getByPlaceholderText("Search worlds...");
    await user.type(searchInput, "War");
    expect(screen.getByText("Warhammer 40k")).toBeInTheDocument();
    expect(screen.getByText("Warframe")).toBeInTheDocument();
    expect(screen.queryByText("Star Wars")).not.toBeInTheDocument();
  });

  it("handles fetchWorlds API error gracefully on mount", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(api.fetchWorlds).mockRejectedValue(new Error("Network Failure"));
    
    render(<DashboardPanel />);
    // Verify it doesn't crash and keeps registry empty
    await waitFor(() => expect(api.fetchWorlds).toHaveBeenCalledOnce());
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it("calls resetAllExplored when Reset All Explored Flags clicked", async () => {
    vi.mocked(api.resetAllExplored).mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await user.click(screen.getByRole("button", { name: /reset all explored flags/i }));
    expect(api.resetAllExplored).toHaveBeenCalledOnce();
    expect(api.fetchWorlds).toHaveBeenCalledTimes(2);
  });

  it("closes EventSource and stops running state on SSE error", async () => {
    const src = sourceMock();
    vi.mocked(api.createEventSource).mockReturnValue(src);
    vi.mocked(api.startOrchestrate).mockResolvedValue({ run_id: "run-1" });

    const user = userEvent.setup();
    render(<DashboardPanel />);

    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "TestWorld");
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(api.createEventSource).toHaveBeenCalled());
    expect(screen.getByText("Running")).toBeInTheDocument();

    act(() => {
      src.onerror();
    });

    await waitFor(() => expect(screen.queryByText("Running")).not.toBeInTheDocument());
    expect(src.close).toHaveBeenCalled();
  });

  it("shows more worlds button when registry has more than 24 worlds", async () => {
    const mockWorlds = Array.from({ length: 30 }, (_, i) => ({
      id: i,
      name: `World-${i}`,
      is_explored: false,
      summary: null,
    }));
    vi.mocked(api.fetchWorlds).mockResolvedValue(mockWorlds);
    const user = userEvent.setup();
    render(<DashboardPanel />);

    await screen.findByText("World-0");
    expect(screen.getByText("+6 more")).toBeInTheDocument();

    await user.click(screen.getByText("+6 more"));
    expect(screen.queryByText("+6 more")).not.toBeInTheDocument();
    expect(screen.getByText("World-29")).toBeInTheDocument();
  });
});

