import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProviderRecord } from "../../src/types";
import * as api from "../api";
import ProviderCard from "../components/settings/ProviderCard";

vi.mock("../api", () => ({
	fetchProviderModels: vi.fn(),
}));

function makeProvider(overrides: Partial<ProviderRecord> = {}) {
	return {
		id: 1,
		name: "Test Provider",
		provider_type: "openai",
		base_url: null,
		models: "gpt-4,gpt-3.5-turbo",
		keys: [
			{ id: 1, provider_id: 1, api_key: "sk-real-key-12345", priority: 0 },
		],
		...overrides,
	} as ProviderRecord;
}

describe("ProviderCard", () => {
	const onSave = vi.fn().mockResolvedValue(undefined);
	const onSaveKey = vi.fn().mockResolvedValue(undefined);
	const onDeleteKey = vi.fn().mockResolvedValue(undefined);
	const onDeleteProvider = vi.fn().mockResolvedValue(undefined);

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(api.fetchProviderModels).mockResolvedValue({
			models: ["gpt-4-turbo"],
		});
	});

	it("renders provider name and type badge", () => {
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		expect(screen.getByDisplayValue("Test Provider")).toBeInTheDocument();
		expect(
			screen.getByText(
				(content, element) =>
					element?.tagName.toLowerCase() === "span" && content === "OpenAI",
			),
		).toBeInTheDocument();
	});

	it("saves provider name on Save Name click", async () => {
		const user = userEvent.setup();
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		const nameInput = screen.getByDisplayValue("Test Provider");
		await user.clear(nameInput);
		await user.type(nameInput, "Renamed Provider");
		await user.click(screen.getByRole("button", { name: /save name/i }));
		expect(onSave).toHaveBeenCalledWith({ id: 1, name: "Renamed Provider" });
	});

	it("saves provider type on select change", async () => {
		const user = userEvent.setup();
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		const select = screen.getByRole("combobox");
		await user.selectOptions(select, "anthropic");
		await waitFor(() => expect(onSave).toHaveBeenCalled());
		const call = onSave.mock.calls.find(
			(c: unknown[]) =>
				(c[0] as { provider_type: string }).provider_type === "anthropic",
		);
		expect(call).toBeTruthy();
	});

	it("shows base URL section for custom type and saves it", async () => {
		const provider = makeProvider({
			provider_type: "custom",
			base_url: "https://my-custom-api.com/v1",
		});
		const user = userEvent.setup();
		render(
			<ProviderCard
				provider={provider}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		expect(
			screen.getByText(
				(content, element) =>
					element?.tagName.toLowerCase() === "h4" && content === "Base URL",
			),
		).toBeInTheDocument();
		const urlInput = screen.getByDisplayValue("https://my-custom-api.com/v1");
		await user.clear(urlInput);
		await user.type(urlInput, "https://new-url.com/v1");
		// Click the Save button in the Base URL section
		const baseUrlHeader = screen.getByText(
			(content, element) =>
				element?.tagName.toLowerCase() === "h4" && content === "Base URL",
		);
		const baseUrlSection = baseUrlHeader.closest(
			".provider-section",
		) as HTMLElement;
		const baseSaveBtn = within(baseUrlSection).getByRole("button", {
			name: /^save$/i,
		});
		await user.click(baseSaveBtn);
		expect(onSave).toHaveBeenCalledWith(
			expect.objectContaining({ base_url: "https://new-url.com/v1" }),
		);
	});

	it("renders existing model tags from provider.models", () => {
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		expect(screen.getByText("gpt-4")).toBeInTheDocument();
		expect(screen.getByText("gpt-3.5-turbo")).toBeInTheDocument();
	});

	it("adds a model tag by typing into tag input and pressing Enter", async () => {
		const user = userEvent.setup();
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		const tagInput = screen.getByPlaceholderText("+ add model");
		await user.type(tagInput, "gpt-4-turbo{Enter}");
		expect(screen.getByText("gpt-4-turbo")).toBeInTheDocument();
	});

	it("removes a model tag when × is clicked on the tag", async () => {
		const user = userEvent.setup();
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		// Find the × button adjacent to the gpt-4 tag
		const gpt4tag = screen
			.getByText("gpt-4")
			.closest(".model-row") as HTMLElement;
		const removeBtn = within(gpt4tag).getByRole("button");
		await user.click(removeBtn);
		expect(screen.queryByText("gpt-4")).not.toBeInTheDocument();
		// gpt-3.5-turbo should still be there
		expect(screen.getByText("gpt-3.5-turbo")).toBeInTheDocument();
	});

	it("shows warning badge when provider has no keys", () => {
		render(
			<ProviderCard
				provider={makeProvider({ keys: [] })}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		expect(screen.getByText(/0 keys/i)).toBeInTheDocument();
	});

	it("calls fetchProviderModels on Sync Saved Models click and merges result", async () => {
		vi.mocked(api.fetchProviderModels).mockResolvedValue({
			models: ["gpt-4-turbo", "o1"],
		});
		const user = userEvent.setup();
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		await user.click(
			screen.getByRole("button", { name: /sync saved models/i }),
		);
		await waitFor(() =>
			expect(api.fetchProviderModels).toHaveBeenCalledWith(1),
		);
		// New models from API should be merged in
		await screen.findByText("o1");
		expect(screen.getByText("o1")).toBeInTheDocument();
	});

	it("masks API key display (shows only last 4 chars)", () => {
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		// The masked key should show ● characters followed by last 4 chars of "sk-real-key-12345"
		const maskedEl = screen.getByText(/●+2345/);
		expect(maskedEl).toBeInTheDocument();
	});

	it("shows confirm-delete UI when Delete provider is clicked, then cancels", async () => {
		const user = userEvent.setup();
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		await user.click(screen.getByRole("button", { name: /^delete$/i }));
		expect(screen.getByText(/delete provider\?/i)).toBeInTheDocument();
		await user.click(screen.getByRole("button", { name: /no/i }));
		expect(screen.queryByText(/delete provider\?/i)).not.toBeInTheDocument();
		expect(onDeleteProvider).not.toHaveBeenCalled();
	});

	it("calls onDeleteProvider when delete is confirmed", async () => {
		const user = userEvent.setup();
		render(
			<ProviderCard
				provider={makeProvider()}
				onSave={onSave}
				onSaveKey={onSaveKey}
				onDeleteKey={onDeleteKey}
				onDeleteProvider={onDeleteProvider}
			/>,
		);
		await user.click(screen.getByRole("button", { name: /^delete$/i }));
		await user.click(screen.getByRole("button", { name: /yes/i }));
		expect(onDeleteProvider).toHaveBeenCalledWith(1);
	});
});
