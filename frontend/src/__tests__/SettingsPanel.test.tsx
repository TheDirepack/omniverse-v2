import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import SettingsPanel from "../components/settings/SettingsPanel";

vi.mock("../api", () => ({
	fetchSettings: vi.fn(),
	fetchProviders: vi.fn(),
	fetchAgentRoutes: vi.fn(),
	fetchAgentNames: vi.fn(),
	saveProvider: vi.fn(),
	saveGeneralSetting: vi.fn(),
	saveProviderKey: vi.fn(),
	deleteProviderKey: vi.fn(),
	deleteProvider: vi.fn(),
	saveAgentRoute: vi.fn(),
	deleteAgentRoute: vi.fn(),
}));

describe("SettingsPanel", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(api.fetchSettings).mockResolvedValue({
			general_settings: {},
			providers: [],
			agent_routes: [],
		});
		vi.mocked(api.fetchProviders).mockResolvedValue([]);
		vi.mocked(api.fetchAgentRoutes).mockResolvedValue([]);
		vi.mocked(api.fetchAgentNames).mockResolvedValue([]);
	});

	it("loads data via 4 API calls on mount", async () => {
		render(<SettingsPanel />);
		await waitFor(() => {
			expect(api.fetchSettings).toHaveBeenCalledOnce();
			expect(api.fetchProviders).toHaveBeenCalledOnce();
			expect(api.fetchAgentRoutes).toHaveBeenCalledOnce();
			expect(api.fetchAgentNames).toHaveBeenCalledOnce();
		});
	});

	it("renders 3 settings tab buttons", async () => {
		render(<SettingsPanel />);
		await screen.findByRole("button", { name: "Providers & Keys" });
		expect(
			screen.getByRole("button", { name: "Providers & Keys" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "Agent Routing" }),
		).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "General" })).toBeInTheDocument();
	});

	it("defaults to providers tab", async () => {
		render(<SettingsPanel />);
		await screen.findByRole("button", { name: "Providers & Keys" });
		const providersTab = screen.getByRole("button", {
			name: "Providers & Keys",
		});
		expect(providersTab).toHaveClass("active");
	});

	it("switches to General tab and shows settings", async () => {
		vi.mocked(api.fetchSettings).mockResolvedValue({
			general_settings: { test_key: "test_val" },
			providers: [],
			agent_routes: [],
		});
		const user = userEvent.setup();
		render(<SettingsPanel />);
		await screen.findByText("General");
		await user.click(screen.getByRole("button", { name: "General" }));
		expect(screen.getByRole("button", { name: "General" })).toHaveClass(
			"active",
		);
		await screen.findByText("test_key");
		expect(screen.getByDisplayValue("test_val")).toBeInTheDocument();
	});

	it("switches to Routing tab", async () => {
		const user = userEvent.setup();
		render(<SettingsPanel />);
		await screen.findByText("Agent Routing");
		await user.click(screen.getByRole("button", { name: "Agent Routing" }));
		expect(screen.getByRole("button", { name: "Agent Routing" })).toHaveClass(
			"active",
		);
	});

	it("calls saveProvider on Add Provider click", async () => {
		vi.mocked(api.saveProvider).mockResolvedValue({});
		const user = userEvent.setup();
		render(<SettingsPanel />);
		await screen.findByText("+ Add Provider");
		await user.click(screen.getByRole("button", { name: "+ Add Provider" }));
		expect(api.saveProvider).toHaveBeenCalledOnce();
		expect(api.saveProvider.mock.calls[0][0].name).toMatch(/^New Provider/);
		await waitFor(() => expect(api.fetchProviders).toHaveBeenCalledTimes(2));
	});

	it("adds a new general setting via input + button", async () => {
		vi.mocked(api.saveGeneralSetting).mockResolvedValue({});
		const user = userEvent.setup();
		render(<SettingsPanel />);
		await screen.findByText("General");
		await user.click(screen.getByRole("button", { name: "General" }));

		const addInput = screen.getByPlaceholderText("Setting Key (e.g. API_KEY)");
		await user.type(addInput, "MY_CUSTOM_KEY");
		await user.click(screen.getByRole("button", { name: /add key/i }));
		expect(api.saveGeneralSetting).toHaveBeenCalledWith("MY_CUSTOM_KEY", null);
		await screen.findByText("MY_CUSTOM_KEY");
	});

	it("renders provider cards when providers exist", async () => {
		vi.mocked(api.fetchProviders).mockResolvedValue([
			{
				id: 1,
				name: "OpenAI",
				provider_type: "openai",
				base_url: null,
				models: "gpt-4",
				keys: [],
			},
		]);
		render(<SettingsPanel />);
		// Search for OpenAI in a way that doesn't match the option in the select dropdown
		const nameInput = await screen.findByPlaceholderText("Provider name");
		await waitFor(() => expect(nameInput.value).toBe("OpenAI"));
		expect(nameInput).toBeInTheDocument();
	});

	it("renders routing section with DEFAULT and agent cards", async () => {
		vi.mocked(api.fetchAgentNames).mockResolvedValue([
			"Researcher",
			"Chronicler",
		]);
		vi.mocked(api.fetchAgentRoutes).mockResolvedValue([
			{
				id: 1,
				task_type: "DEFAULT",
				provider_id: null,
				models: null,
				priority: 0,
			},
		]);
		const user = userEvent.setup();
		render(<SettingsPanel />);
		await screen.findByText("Agent Routing");
		await user.click(screen.getByRole("button", { name: "Agent Routing" }));
		await screen.findByText("DEFAULT");
		expect(screen.getByText("DEFAULT")).toBeInTheDocument();
		expect(screen.getByText("Researcher")).toBeInTheDocument();
		expect(screen.getByText("Chronicler")).toBeInTheDocument();
	});
});
