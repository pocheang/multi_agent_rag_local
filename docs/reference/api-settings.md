# API Settings Guide

**最后更新**: 2026-04-28


The API settings panel lets each logged-in user choose the chat model provider used by new query requests.

## Access

1. Log in at `http://localhost:8000/app`.
2. Click `设置` in the top action bar.
3. Edit the model API settings in the right-side panel.

For Vite dev mode, you can also open `http://localhost:5173/app`.

## Supported Providers

- `ollama`: local Ollama service, no API key required.
- `openai`: OpenAI-compatible API with API key.
- `deepseek`: DeepSeek API, treated as OpenAI-compatible.
- `anthropic`: Anthropic API with API key.
- `custom`: any OpenAI-compatible endpoint.

## Fields

- `Provider`: model provider.
- `API Key`: required for cloud providers.
- `Base URL`: API endpoint.
- `Model`: model name.
- `Temperature`: generation randomness, from `0` to `2`.
- `Max Tokens`: output token limit, from `256` to `8192`.

## Runtime Behavior

Settings are stored per user through `GET/POST /user/api-settings`. New `/query` and `/query/stream` requests load the current user's saved settings and apply them to chat and reasoning model calls. Embedding models still use the global server configuration so existing vector indexes remain stable.

## Troubleshooting

- If the panel does not open, make sure you are on `/app`.
- If settings fail to save, confirm the backend is running and that `/user` is proxied by the frontend dev server.
- If a cloud provider returns authentication errors during chat, recheck the API key and account credits.
- If login succeeds but you appear logged out, make sure frontend URL host and `VITE_API_BASE_URL` host are consistent (do not mix `localhost` and `127.0.0.1`).
