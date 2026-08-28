# Model Temperature Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure current GLM/custom chat requests never receive a temperature outside `0–1`, while both frontend model-setting surfaces expose and submit only `0–1`.

**Architecture:** Preserve the existing global-model priority chain and RAGPipeline flow. Enforce the contract at three boundaries: persisted/request schemas, provider-aware runtime construction, and frontend controls/payload construction. Keep OpenAI-compatible providers that support temperatures above `1` unchanged internally, except that the two frontend settings surfaces intentionally expose only `0–1`.

**Tech Stack:** FastAPI, Pydantic v2, Python 3.11, React 18, TypeScript, Vitest, jsdom, Vite.

## Global Constraints

- Casual chat temperature is exactly `0.9`.
- Both frontend temperature sliders use `min=0`, `max=1`, `step=0.1`.
- Frontend save and connectivity-test payloads normalize temperature to `0–1`.
- `AdminModelSettings`, `AdminModelSettingsView`, `UserApiSettings`, and `UserApiSettingsView` accept only `0–1`.
- Legacy persisted global settings above `1` normalize safely to `1`.
- The final runtime temperature for provider `custom` is limited to `0–1`; native ranges for other providers are not narrowed in the runtime builder.
- Do not change RAGPipeline routing, Profile behavior, SSE event names/data, API keys, Base URLs, model names, or response structures.
- Use `conda run -n rag-local` for every Python command.
- Preserve unrelated dirty-worktree changes and do not commit, reset, checkout, or clean the shared working tree.

---

### Task 1: Enforce the model-temperature contract end to end

**Files:**
- Modify: `app/agents/synthesizer/generation.py`
- Modify: `app/services/models/runtime.py`
- Modify: `app/services/models/config_store.py`
- Modify: `app/api/schemas/http.py`
- Modify: `tests/test_agent_resilience.py`
- Modify: `tests/test_model_provider_config.py`
- Modify: `frontend/src/pages/admin/AdminModelSettings.tsx`
- Modify: `frontend/src/pages/admin/actions/modelActions.ts`
- Modify: `frontend/src/components/ApiSettingsFormFields.tsx`
- Modify: `frontend/src/components/apiSettingsUtils.ts`
- Create: `frontend/src/lib/model-temperature.ts`
- Create: `frontend/src/lib/model-temperature.test.ts`
- Create or modify focused real-render tests for `AdminModelSettings` and `ApiSettingsFormFields` only if existing tests cannot assert their rendered range attributes.

**Interfaces:**
- Consumes: existing `get_chat_model(temperature?: number)`, global/user model-setting request schemas, `AdminModelSettingsView`, and `ApiConfig`.
- Produces: `normalizeModelTemperature(value: number, fallback?: number): number`, returning a finite number in `[0,1]`; provider-aware backend temperature normalization used before constructing the concrete chat model.

- [ ] **Step 1: Add failing backend tests for the confirmed regression**

  In `tests/test_agent_resilience.py`, change the casual-chat behavior assertion to a hand-derived literal and assert that the generation model receives exactly `0.9`, not the production constant.

  In `tests/test_model_provider_config.py`, add tests with these observable expectations:

  ```python
  def test_model_setting_schemas_reject_temperature_above_one():
      with pytest.raises(ValidationError):
          AdminModelSettings(temperature=1.1)
      with pytest.raises(ValidationError):
          UserApiSettings(temperature=1.1)


  def test_legacy_global_temperature_is_normalized_to_one():
      normalized = normalize_global_model_settings({"provider": "local", "temperature": 1.7})
      assert normalized["temperature"] == 1.0


  def test_custom_runtime_temperature_is_bounded_without_narrowing_openai(monkeypatch):
      # Capture the temperature passed to the concrete model builder.
      # custom + 2.0 must produce 1.0; openai + 2.0 must remain 2.0.
  ```

  Mock only configuration/model construction; do not call an external model in unit tests.

- [ ] **Step 2: Run backend tests and verify RED**

  Run:

  ```powershell
  conda run -n rag-local pytest tests/test_agent_resilience.py::test_synthesize_uses_high_temperature_for_casual_chat tests/test_model_provider_config.py -v
  ```

  Expected: failures show current `2.0`, Schema upper bound `2.0`, legacy normalization to `1.7`, or custom runtime forwarding `2.0`.

- [ ] **Step 3: Implement the minimal backend fix**

  - Set `CASUAL_CHAT_HIGH_TEMPERATURE = 0.9`.
  - Change the four public model-setting Schema temperature upper bounds from `2.0` to `1.0`.
  - Change global-setting normalization from `min(2.0, ...)` to `min(1.0, ...)`.
  - Add a small provider-aware runtime normalizer. It clamps non-finite/low values safely and caps only `custom` at `1.0`; it must preserve `2.0` for provider `openai`.
  - Apply it to the final temperature passed into chat-model construction for global, per-request, and environment paths without changing provider selection or credentials.

- [ ] **Step 4: Run backend tests and verify GREEN**

  Run the exact command from Step 2. Expected: all selected tests pass with zero failures.

- [ ] **Step 5: Add failing frontend tests for controls and payloads**

  Create `frontend/src/lib/model-temperature.test.ts` with hand-derived cases:

  ```typescript
  expect(normalizeModelTemperature(-0.2)).toBe(0);
  expect(normalizeModelTemperature(0.7)).toBe(0.7);
  expect(normalizeModelTemperature(1.4)).toBe(1);
  expect(normalizeModelTemperature(Number.NaN, 0.7)).toBe(0.7);
  ```

  Add focused real-render assertions that both temperature range inputs expose `min="0"`, `max="1"`, and `step="0.1"`. Add behavior coverage proving both admin and user save/test payload construction normalizes an old `1.4` state to `1`.

- [ ] **Step 6: Run frontend focused tests and verify RED**

  Run:

  ```powershell
  cd frontend
  npm.cmd test -- --run src/lib/model-temperature.test.ts src/pages/admin src/components
  ```

  Expected: failures show current slider `max=2` and payload maximum `2` or missing shared normalizer.

- [ ] **Step 7: Implement the minimal frontend fix**

  - Add `normalizeModelTemperature` in `frontend/src/lib/model-temperature.ts`.
  - Use it in `modelActions.ts` and `apiSettingsUtils.ts` for save/test payloads and parsing legacy responses.
  - Set both range controls to `min=0`, `max=1`, `step=0.1`.
  - Normalize the value passed through each range `onChange` so stale state cannot reintroduce values above `1`.
  - Do not add `any`; if touching `parseApiResponse`, replace its existing `any` parameter only when the current API type is already available without unrelated refactoring.

- [ ] **Step 8: Run frontend focused tests and verify GREEN**

  Run the exact command from Step 6. Expected: all selected tests pass with zero failures.

- [ ] **Step 9: Run complete automated verification**

  Run:

  ```powershell
  conda run -n rag-local pytest tests/test_agent_resilience.py tests/test_model_provider_config.py tests/test_user_api_settings_test_api.py -v
  conda run -n rag-local ruff check app/agents/synthesizer/generation.py app/services/models/runtime.py app/services/models/config_store.py app/api/schemas/http.py tests/test_agent_resilience.py tests/test_model_provider_config.py
  cd frontend
  npm.cmd test -- --run
  npm.cmd run build
  cd ..
  git diff --check -- app frontend tests
  ```

  The repository has no frontend lint script, so the TypeScript build and Vitest suite are the frontend static checks.

- [ ] **Step 10: Runtime verification after automatic reload/restart**

  - Confirm `http://127.0.0.1:5173/` and `http://127.0.0.1:8000/health` return HTTP 200.
  - Use the existing backend connectivity probe with the persisted global settings and only override temperature to `0.9`; require `reachable=true` and preview `OK`.
  - Exercise one authenticated standard `/query/stream` request when the existing browser session is available. Confirm the stream reaches its terminal completed event and the answer is not `SYNTHESIS_FALLBACK_MESSAGE`.
  - If browser credentials/session cannot be accessed, report the exact unexecuted scenario and use the real provider probe plus regression tests as the substitute; do not call the authenticated query verified.

- [ ] **Step 11: Review the final diff**

  Confirm the diff contains only temperature-contract code/tests plus the approved spec/plan artifacts, no credential values, no response-contract changes, and no unrelated cleanup.
