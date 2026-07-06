export type Provider = "local" | "openai" | "anthropic" | "deepseek" | "ollama" | "custom";

export type ApiConfig = {
  provider: Provider;
  apiKey: string;
  apiKeyMasked: string;
  baseUrl: string;
  model: string;
  temperature: number;
  maxTokens: number;
  globalOverrideEnabled?: boolean;
  globalProvider?: string;
  globalModel?: string;
  effectiveProvider?: string;
  effectiveModel?: string;
};

export const PROVIDER_MODELS: Record<Provider, string[]> = {
  local: ["local-evidence"],
  openai: ["gpt-5.5", "gpt-5-mini"],
  anthropic: ["claude-sonnet-5", "claude-fable-5", "claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"],
  deepseek: ["deepseek-v4-flash", "deepseek-v4-pro"],
  ollama: ["qwen2.5:7b-instruct", "qwen2.5:14b-instruct", "qwen3:235b", "qwen3:70b", "qwen3:14b", "qwen3:7b", "qwen3-coder:235b", "qwen3-coder:70b", "llama4-scout:70b", "llama4-scout:8b", "deepseek-v4", "deepseek-r1:70b", "deepseek-r1:32b", "gemma3:27b", "gemma3:9b", "nomic-embed-text"],
  custom: [],
};

export const PROVIDER_DEFAULTS: Record<Provider, Pick<ApiConfig, "baseUrl" | "model">> = {
  local: { baseUrl: "", model: "local-evidence" },
  openai: { baseUrl: "https://api.openai.com/v1", model: "gpt-5.5" },
  anthropic: { baseUrl: "https://api.anthropic.com", model: "claude-sonnet-5" },
  deepseek: { baseUrl: "https://api.deepseek.com/v1", model: "deepseek-v4-flash" },
  ollama: { baseUrl: "http://localhost:11434", model: "qwen2.5:7b-instruct" },
  custom: { baseUrl: "", model: "" },
};

export const QUICK_PRESETS = [
  { name: "Local Evidence", provider: "local" as Provider, model: "local-evidence", mark: "LC" },
  { name: "Ollama Local", provider: "ollama" as Provider, model: "qwen2.5:7b-instruct", mark: "OL" },
  { name: "OpenAI GPT", provider: "openai" as Provider, model: "gpt-5.5", mark: "OA" },
  { name: "DeepSeek", provider: "deepseek" as Provider, model: "deepseek-v4-flash", mark: "DS" },
  { name: "Claude", provider: "anthropic" as Provider, model: "claude-sonnet-5", mark: "CL" },
];

export const PROVIDERS: Provider[] = ["local", "ollama", "openai", "deepseek", "anthropic", "custom"];

export const DEFAULT_CONFIG: ApiConfig = {
  provider: "local",
  apiKey: "",
  apiKeyMasked: "",
  baseUrl: "",
  model: "local-evidence",
  temperature: 0.7,
  maxTokens: 2048,
};
