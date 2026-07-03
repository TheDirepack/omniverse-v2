import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardPanel from "../frontend/src/components/DashboardPanel";

const mockFetchWorlds = vi.fn();
const mockStartOrchestrate = vi.fn();
const mockResearchUnexplored = vi.fn();
const mockAddWorld = vi.fn();
const mockResetAllExplored = vi.fn();
const mockResetWorldExplored = vi.fn();
const mockRunFocusedSearch = vi.fn();
const mockResetDatabase = vi.fn();
const mockClearLogsApi = vi.fn();
const mockCreateEventSource = vi.fn();

vi.mock("../frontend/src/api", () => ({
  fetchWorlds: mockFetchWorlds,
  startOrchestrate: mockStartOrchestrate,
  researchUnexplored: mockResearchUnexplored,
  addWorld: mockAddWorld,
  resetAllExplored: mockResetAllExplored,
  resetWorldExplored: mockResetWorldExplored,
  runFocusedSearch: mockRunFocusedSearch,
  resetDatabase: mockResetDatabase,
  clearLogsApi: mockClearLogsApi,
  createEventSource: mockCreateEventSource,
}));

function sourceMock() {
  return { onmessage: null as any, onerror: null as any, close: vi.fn() };
}

describe("DashboardPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchWorlds.mockResolvedValue([]);
    mockCreateEventSource.mockReturnValue(sourceMock());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads world registry on mount", async () => {
    mockFetchWorlds.mockResolvedValue([
      { id: 1, name: "Warhammer 40k", is_explored: true, summary: null },
      { id: 2, name: "Star Wars", is_explored: false, summary: null },
    ]);
    render(<DashboardPanel />);
    await screen.findByText("Warhammer 40k");
    expect(screen.getByText("Warhammer 40k")).toBeInTheDocument();
    expect(screen.getByText("Star Wars")).toBeInTheDocument();
    expect(mockFetchWorlds).toHaveBeenCalledOnce();
  });

  it("marks explored worlds with checkmark", async () => {
    mockFetchWorlds.mockResolvedValue([
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
    mockStartOrchestrate.mockResolvedValue({ run_id: "run-1" });
    const user = userEvent.setup();
    render(<DashboardPanel />);
    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "Warhammer 40k, Star Wars");
    await user.click(screen.getByRole("button", { name: /run/i }));
    expect(mockStartOrchestrate).toHaveBeenCalledWith(["Warhammer 40k", "Star Wars"]);
  });

  it("calls researchUnexplored on Research button click", async () => {
    mockResearchUnexplored.mockResolvedValue({ run_id: null, worlds: [], status: "ok" });
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await user.click(screen.getByRole("button", { name: /research all unexplored/i }));
    expect(mockResearchUnexplored).toHaveBeenCalledOnce();
  });

  it("calls addWorld on Add + Research click and refreshes", async () => {
    mockAddWorld.mockResolvedValue({ id: 3, name: "Dune" });
    const user = userEvent.setup();
    render(<DashboardPanel />);
    const input = screen.getByPlaceholderText("Add world to DB");
    await user.type(input, "Dune");
    await user.click(screen.getByRole("button", { name: /add \+ research/i }));
    expect(mockAddWorld).toHaveBeenCalledWith("Dune");
    await waitFor(() => expect(mockFetchWorlds).toHaveBeenCalledTimes(2));
  });

  it("calls resetWorldExplored when world chip clicked", async () => {
    mockFetchWorlds.mockResolvedValue([
      { id: 1, name: "Warhammer 40k", is_explored: true, summary: null },
    ]);
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await screen.findByText(/Warhammer 40k/);
    await user.click(screen.getByText(/Warhammer 40k/));
    expect(mockResetWorldExplored).toHaveBeenCalledWith(1);
    expect(mockFetchWorlds).toHaveBeenCalledTimes(2);
  });

  it("calls runFocusedSearch with world name and feature", async () => {
    mockRunFocusedSearch.mockResolvedValue({ run_id: "fs-1" });
    const user = userEvent.setup();
    render(<DashboardPanel />);
    const worldInput = screen.getByPlaceholderText("World name");
    const featureInput = screen.getByPlaceholderText("Feature to prove/disprove");
    await user.type(worldInput, "Star Wars");
    await user.type(featureInput, "The Force is real");
    await user.click(screen.getByRole("button", { name: /focused search/i }));
    expect(mockRunFocusedSearch).toHaveBeenCalledWith("Star Wars", "The Force is real");
  });

  it("calls resetDatabase on Reset DB click", async () => {
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await screen.findByText("Reset DB");
    await user.click(screen.getByRole("button", { name: /reset db/i }));
    expect(mockResetDatabase).toHaveBeenCalledOnce();
  });

  it("calls clearLogsApi and clears local logs on Clear Logs click", async () => {
    const user = userEvent.setup();
    render(<DashboardPanel />);
    await user.click(screen.getByRole("button", { name: /clear logs/i }));
    expect(mockClearLogsApi).toHaveBeenCalledOnce();
  });

  it("displays SSE logs in Live Logs panel", async () => {
    const src = sourceMock();
    mockCreateEventSource.mockReturnValue(src);
    mockStartOrchestrate.mockResolvedValue({ run_id: "run-1" });

    const user = userEvent.setup();
    render(<DashboardPanel />);

    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "TestWorld");
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(mockCreateEventSource).toHaveBeenCalledWith("run-1"));

    act(() => {
      src.onmessage({ data: JSON.stringify({ node_name: "Researcher", thought: "Analyzing...", status: "running", created_at: "12:00" }) });
    });

    expect(screen.getByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText(/Analyzing\.\.\./)).toBeInTheDocument();
    expect(screen.getByText("12:00")).toBeInTheDocument();
  });

  it("shows Running status pill while SSE is active", async () => {
    const src = sourceMock();
    mockCreateEventSource.mockReturnValue(src);
    mockStartOrchestrate.mockResolvedValue({ run_id: "run-1" });

    const user = userEvent.setup();
    render(<DashboardPanel />);

    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "TestWorld");
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(mockCreateEventSource).toHaveBeenCalled());
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("handles finished SSE message by stopping run", async () => {
    const src = sourceMock();
    mockCreateEventSource.mockReturnValue(src);
    mockStartOrchestrate.mockResolvedValue({ run_id: "run-1" });

    const user = userEvent.setup();
    render(<DashboardPanel />);

    const textarea = screen.getByPlaceholderText("Warhammer 40k, Star Wars, Harry Potter");
    await user.type(textarea, "TestWorld");
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(mockCreateEventSource).toHaveBeenCalled());

    act(() => {
      src.onmessage({ data: JSON.stringify({ finished: true }) });
    });

    await waitFor(() => expect(screen.getByText("Completed")).toBeInTheDocument());
    expect(src.close).toHaveBeenCalled();
  });

  it("shows unexplored count in Research button label", async () => {
    mockFetchWorlds.mockResolvedValue([
      { id: 1, name: "W1", is_explored: false, summary: null },
      { id: 2, name: "W2", is_explored: true, summary: null },
      { id: 3, name: "W3", is_explored: false, summary: null },
    ]);
    render(<DashboardPanel />);
    await screen.findByText(/2 worlds/);
    expect(screen.getByText(/research all unexplored.*2 worlds/i)).toBeInTheDocument();
  });

  it("filters worlds by search term", async () => {
    mockFetchWorlds.mockResolvedValue([
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
});
