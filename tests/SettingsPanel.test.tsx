import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingsPanel from "../frontend/src/components/settings/SettingsPanel";

const mockFetchSettings = vi.fn();
const mockFetchProviders = vi.fn();
const mockFetchAgentRoutes = vi.fn();
const mockFetchAgentNames = vi.fn();
const mockSaveProvider = vi.fn();
const mockSaveGeneralSetting = vi.fn();
const mockSaveProviderKey = vi.fn();
const mockDeleteProviderKey = vi.fn();
const mockDeleteProvider = vi.fn();
const mockSaveAgentRoute = vi.fn();
const mockDeleteAgentRoute = vi.fn();

vi.mock("../frontend/src/api", () => ({
  fetchSettings: mockFetchSettings,
  fetchProviders: mockFetchProviders,
  fetchAgentRoutes: mockFetchAgentRoutes,
  fetchAgentNames: mockFetchAgentNames,
  saveProvider: mockSaveProvider,
  saveGeneralSetting: mockSaveGeneralSetting,
  saveProviderKey: mockSaveProviderKey,
  deleteProviderKey: mockDeleteProviderKey,
  deleteProvider: mockDeleteProvider,
  saveAgentRoute: mockSaveAgentRoute,
  deleteAgentRoute: mockDeleteAgentRoute,
}));

describe("SettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchSettings.mockResolvedValue({ general_settings: {}, providers: [], agent_routes: [] });
    mockFetchProviders.mockResolvedValue([]);
    mockFetchAgentRoutes.mockResolvedValue([]);
    mockFetchAgentNames.mockResolvedValue([]);
  });

  it("loads data via 4 API calls on mount", async () => {
    render(<SettingsPanel />);
    await waitFor(() => {
      expect(mockFetchSettings).toHaveBeenCalledOnce();
      expect(mockFetchProviders).toHaveBeenCalledOnce();
      expect(mockFetchAgentRoutes).toHaveBeenCalledOnce();
      expect(mockFetchAgentNames).toHaveBeenCalledOnce();
    });
  });

  it("renders 3 settings tab buttons", async () => {
    render(<SettingsPanel />);
    await screen.findByText("Providers & Keys");
    expect(screen.getByText("Providers & Keys")).toBeInTheDocument();
    expect(screen.getByText("Agent Routing")).toBeInTheDocument();
    expect(screen.getByText("General")).toBeInTheDocument();
  });

  it("defaults to providers tab", async () => {
    render(<SettingsPanel />);
    await screen.findByText("Providers & Keys");
    const providersTab = screen.getByText("Providers & Keys");
    expect(providersTab.closest("button")).toHaveClass("active");
  });

  it("switches to General tab and shows settings", async () => {
    mockFetchSettings.mockResolvedValue({ general_settings: { test_key: "test_val" }, providers: [], agent_routes: [] });
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByText("General");
    await user.click(screen.getByText("General"));
    expect(screen.getByText("General").closest("button")).toHaveClass("active");
    await screen.findByText("test_key");
    expect(screen.getByDisplayValue("test_val")).toBeInTheDocument();
  });

  it("switches to Routing tab", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByText("Agent Routing");
    await user.click(screen.getByText("Agent Routing"));
    expect(screen.getByText("Agent Routing").closest("button")).toHaveClass("active");
  });

  it("calls saveProvider on Add Provider click", async () => {
    mockSaveProvider.mockResolvedValue({});
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByText("+ Add Provider");
    await user.click(screen.getByText("+ Add Provider"));
    expect(mockSaveProvider).toHaveBeenCalledOnce();
    expect(mockSaveProvider.mock.calls[0][0].name).toMatch(/^New Provider/);
    await waitFor(() => expect(mockFetchProviders).toHaveBeenCalledTimes(2));
  });

  it("adds a new general setting via input + button", async () => {
    mockSaveGeneralSetting.mockResolvedValue({});
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByText("General");
    await user.click(screen.getByText("General"));

    const addInput = screen.getByPlaceholderText("Setting Key (e.g. API_KEY)");
    await user.type(addInput, "MY_CUSTOM_KEY");
    await user.click(screen.getByRole("button", { name: /add key/i }));
    expect(mockSaveGeneralSetting).toHaveBeenCalledWith("MY_CUSTOM_KEY", null);
    await screen.findByText("MY_CUSTOM_KEY");
  });

  it("renders provider cards when providers exist", async () => {
    mockFetchProviders.mockResolvedValue([
      { id: 1, name: "OpenAI", provider_type: "openai", base_url: null, models: "gpt-4", keys: [] },
    ]);
    render(<SettingsPanel />);
    await screen.findByText("OpenAI");
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("renders routing section with DEFAULT and agent cards", async () => {
    mockFetchAgentNames.mockResolvedValue(["Researcher", "Chronicler"]);
    mockFetchAgentRoutes.mockResolvedValue([
      { id: 1, task_type: "DEFAULT", provider_id: null, models: null, priority: 0 },
    ]);
    render(<SettingsPanel />);
    await userEvent.setup().click(await screen.findByText("Agent Routing"));
    await screen.findByText("DEFAULT");
    expect(screen.getByText("DEFAULT")).toBeInTheDocument();
    expect(screen.getByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText("Chronicler")).toBeInTheDocument();
  });
});
