# Fill in API keys or base URLs to enable live provider model tests.
# Unconfigured providers are skipped with a warning.
# Run: python -m pytest tests/ -v --tb=short -m "slow" -rs

PROVIDER_CREDENTIALS = {
    "openai":     {"api_key": "", "base_url": None, "model": ""},
    "anthropic":  {"api_key": "", "base_url": None, "model": ""},
    "gemini":     {"api_key": "", "base_url": None, "model": "Gemma-4-26B"},
    "ollama":     {"api_key": None, "base_url": "", "model": ""},  # set base_url to "http://localhost:11434" to test
    "groq":       {"api_key": "", "base_url": None, "model": ""},
    "openrouter": {"api_key": "", "base_url": None, "model": ""},
    "custom":     {"api_key": None, "base_url": "http://localhost:8000/v1", "model": "bartowski/Llama-3.2-1B-Instruct-GGUF:Q4_K_M"},  # set base_url to "http://localhost:8000/v1" to test
}
