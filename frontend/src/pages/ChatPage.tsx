import { useEffect, useMemo, useRef, useState } from "react";
import type React from "react";
import { ApiError, appApi } from "@/lib/api";
import type { Citation, IndexedFileSummary, PromptTemplate, SessionMessage, SessionSummary } from "@/types/api";
import {
  EMPTY_METADATA,
  QUICK_PROMPTS,
  SUPPORTED_CHAT_RE,
  SUPPORTED_DOC_RE,
  isMobile,
  mapRunStatus,
} from "@/pages/chat/constants";
import type { Props, Toast } from "@/pages/chat/types";
import { ChatTopbar } from "@/pages/chat/components/ChatTopbar";
import { ChatMessages } from "@/pages/chat/components/ChatMessages";
import { ChatComposer } from "@/pages/chat/components/ChatComposer";
import { ToastStack } from "@/pages/chat/components/ToastStack";

type AgentClassHint = "" | "general" | "cybersecurity" | "artificial_intelligence" | "pdf_text";
const PDF_FILE_RE = /\.(pdf|png|jpe?g|bmp|tiff?|webp)$/i;

const AGENT_MODES: Array<{
  key: AgentClassHint;
  title: string;
  desc: string;
}> = [
  { key: "", title: "Auto Router", desc: "Automatically route by user intent and context." },
  { key: "cybersecurity", title: "Cybersecurity", desc: "Threat analysis, incident response, and hardening." },
  { key: "artificial_intelligence", title: "AI Research", desc: "LLM, RAG, and model/system design questions." },
  { key: "pdf_text", title: "PDF Reader", desc: "Focus on PDF/image document Q&A and evidence extraction." },
  { key: "general", title: "General Analyst", desc: "Cross-domain summaries and executive reporting." },
];

export function ChatPage({ user, onLogout, themeLabel, onThemeToggle }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [runStatus, setRunStatus] = useState("");
  const [useWeb, setUseWeb] = useState(false);
  const [useReasoning, setUseReasoning] = useState(false);
  const [agentClassHint, setAgentClassHint] = useState<AgentClassHint>("");
  const [pdfTargetFile, setPdfTargetFile] = useState("");

  const [documents, setDocuments] = useState<IndexedFileSummary[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadInfo, setUploadInfo] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadProgressText, setUploadProgressText] = useState("");
  const [uploadVisibility, setUploadVisibility] = useState<"private" | "public">("private");
  const [docDropActive, setDocDropActive] = useState(false);
  const [composerDropActive, setComposerDropActive] = useState(false);
  const [busySessionId, setBusySessionId] = useState<string | null>(null);

  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptTitle, setPromptTitle] = useState("");
  const [promptContent, setPromptContent] = useState("");
  const [editingPromptId, setEditingPromptId] = useState<string | null>(null);
  const [promptCheckInfo, setPromptCheckInfo] = useState("");

  const [toasts, setToasts] = useState<Toast[]>([]);
  const [error, setError] = useState("");

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatUploadInputRef = useRef<HTMLInputElement | null>(null);
  const questionRef = useRef<HTMLTextAreaElement | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  const role = (user?.role || "viewer").toLowerCase();
  const isAdmin = role === "admin";
  const canUploadAndManageDocs = true;
  const userBadge = user ? `${user.username} (${role})` : "unknown";
  const pdfDocuments = useMemo(
    () => documents.filter((doc) => PDF_FILE_RE.test(doc.filename || "")),
    [documents],
  );
  const nonPdfDocuments = useMemo(
    () => documents.filter((doc) => !PDF_FILE_RE.test(doc.filename || "")),
    [documents],
  );
  const pdfNeedingReindex = useMemo(
    () => pdfDocuments.filter((doc) => (doc.chunks || 0) <= 0),
    [pdfDocuments],
  );
  const agentDistribution = useMemo(() => {
    const counts = new Map<string, number>();
    for (const doc of documents) {
      const key = (doc.agent_class || "general").trim() || "general";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([agent, count]) => ({ agent, count }))
      .sort((a, b) => b.count - a.count);
  }, [documents]);

  const notify = (text: string, kind: Toast["kind"] = "info", ttl = 2400) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev, { id, text, kind }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), ttl);
  };

  const closeSidebar = () => {
    if (isMobile()) setSidebarOpen(false);
  };

  useEffect(() => {
    if (!pdfDocuments.length) {
      setPdfTargetFile("");
      return;
    }
    if (!pdfTargetFile || !pdfDocuments.some((doc) => doc.filename === pdfTargetFile)) {
      setPdfTargetFile(pdfDocuments[0]?.filename || "");
    }
  }, [pdfDocuments, pdfTargetFile]);

  const handleApiError = async (e: unknown, fallback: string) => {
    if (e instanceof ApiError && e.status === 401) {
      notify("Session expired. Please log in again.", "error");
      await onLogout();
      return;
    }
    const msg = e instanceof Error ? e.message : fallback;
    setError(msg);
    notify(msg, "error");
  };

  const switchAgentMode = (next: AgentClassHint) => {
    setAgentClassHint(next);
    notify(`Mode switched to ${next || "auto"}`, "success");
  };

  const draftPdfQuestion = () => {
    if (!pdfDocuments.length) {
      notify("No PDF/image docs available. Upload first.", "warn");
      return;
    }
    const target = pdfTargetFile || pdfDocuments[0]?.filename || "";
    if (!target) return;
    setAgentClassHint("pdf_text");
    setQuestion(`Read "${target}" and provide key points, major risks, and supporting evidence.`);
    questionRef.current?.focus();
    notify("Drafted a PDF-focused question.", "success");
  };

  const loadSession = async (sessionId: string) => {
    setBusySessionId(sessionId);
    try {
      const detail = await appApi.sessionDetail(sessionId);
      setCurrentSessionId(detail.session_id);
      setMessages(detail.messages || []);
      setError("");
      closeSidebar();
    } catch (e) {
      await handleApiError(e, "Failed to load session");
    } finally {
      setBusySessionId(null);
    }
  };

  const refreshSessions = async (preferSelectFirst = false, silent = false) => {
    if (!silent) setSessionLoading(true);
    try {
      const rows = await appApi.sessions();
      setSessions(rows);
      setError("");
      if (preferSelectFirst && rows.length > 0) await loadSession(rows[0].session_id);
      return rows;
    } catch (e) {
      await handleApiError(e, "Failed to refresh sessions");
      return [] as SessionSummary[];
    } finally {
      if (!silent) setSessionLoading(false);
    }
  };

  const createSession = async () => {
    try {
      const detail = await appApi.sessionCreate();
      setCurrentSessionId(detail.session_id);
      setMessages(detail.messages || []);
      await refreshSessions();
      notify("Session created", "success");
      closeSidebar();
      return detail.session_id;
    } catch (e) {
      await handleApiError(e, "Failed to create session");
      return null;
    }
  };

  const deleteSession = async (sessionId: string) => {
    if (!window.confirm("Delete this session?")) return;
    try {
      await appApi.sessionDelete(sessionId);
      if (sessionId === currentSessionId) {
        setCurrentSessionId(null);
        setMessages([]);
      }
      await refreshSessions();
      notify("Session deleted", "success");
    } catch (e) {
      await handleApiError(e, "Failed to delete session");
    }
  };

  const refreshDocuments = async (silent = false) => {
    if (!silent) setDocsLoading(true);
    try {
      const rows = await appApi.documents();
      setDocuments(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, "Failed to load documents");
    } finally {
      if (!silent) setDocsLoading(false);
    }
  };

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return;
    if (!canUploadAndManageDocs) {
      notify("Upload permission denied", "warn");
      return;
    }
    try {
      setUploading(true);
      setUploadProgress(0);
      setUploadProgressText("Preparing upload...");
      setUploadInfo("Uploading...");
      const data = await appApi.upload(
        files,
        (percent) => {
          setUploadProgress(percent);
          setUploadProgressText(`Uploading ${Math.round(percent)}%`);
        },
        uploadVisibility,
      );
      setUploadProgress(100);
      setUploadProgressText("Upload complete");
      setUploadInfo(
        `Indexed: ${data.filenames.join(", ")} | Skipped: ${(data.skipped_files || []).join(", ") || "none"} | Visibility: ${data.visibility_applied || uploadVisibility} | docs=${data.loaded_documents}, chunks=${data.chunks_indexed}, triplets=${data.triplets_written}`,
      );
      const classes = Object.values(data.assigned_agent_classes || {}).filter(Boolean);
      if (classes.length > 0) {
        const unique = Array.from(new Set(classes));
        if (unique.length === 1) setAgentClassHint((unique[0] as AgentClassHint) || "");
      }
      notify(`Upload completed: ${data.filenames.join(", ")}`, "success");
      await refreshDocuments();
    } catch (e) {
      setUploadInfo(`Upload failed: ${e instanceof Error ? e.message : "unknown error"}`);
      await handleApiError(e, "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (chatUploadInputRef.current) chatUploadInputRef.current.value = "";
      window.setTimeout(() => {
        setUploadProgress(0);
        setUploadProgressText("");
      }, 900);
    }
  };

  const onMainUploadChange = async (evt: React.ChangeEvent<HTMLInputElement>) => {
    await uploadFiles(Array.from(evt.target.files || []));
  };

  const onChatUploadChange = async (evt: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(evt.target.files || []).filter((f) => SUPPORTED_CHAT_RE.test(f.name));
    if (!files.length) {
      notify("This area supports PDF/image files only", "warn");
      return;
    }
    await uploadFiles(files);
  };

  const onDocsDrop = async (evt: React.DragEvent<HTMLDivElement>) => {
    evt.preventDefault();
    evt.stopPropagation();
    setDocDropActive(false);
    const files = Array.from(evt.dataTransfer.files || []).filter((f) => SUPPORTED_DOC_RE.test(f.name));
    if (!files.length) {
      notify("Only .md / .txt / .pdf / image files are supported", "warn");
      return;
    }
    await uploadFiles(files);
  };

  const onComposerDrop = async (evt: React.DragEvent<HTMLElement>) => {
    evt.preventDefault();
    evt.stopPropagation();
    setComposerDropActive(false);
    const files = Array.from(evt.dataTransfer.files || []).filter((f) => SUPPORTED_CHAT_RE.test(f.name));
    if (!files.length) {
      notify("This area supports PDF/image files only", "warn");
      return;
    }
    await uploadFiles(files);
  };

  const deleteDocument = async (item: IndexedFileSummary, removeFile: boolean) => {
    if (!canUploadAndManageDocs) {
      notify("No document management permission", "warn");
      return;
    }
    const verb = removeFile ? "Delete file and index" : "Delete index";
    if (!window.confirm(`${verb}: ${item.filename} ?`)) return;
    try {
      const res = await appApi.documentDelete(item.filename, item.source, removeFile);
      setUploadInfo(
        `${item.filename}: chunks_removed=${res.chunks_removed}, triplets_removed=${res.triplets_removed}, file_removed=${res.file_removed}`,
      );
      notify(`${item.filename} deleted`, "success");
      await refreshDocuments();
    } catch (e) {
      await handleApiError(e, "Failed to delete document");
    }
  };

  const reindexDocument = async (item: IndexedFileSummary) => {
    if (!canUploadAndManageDocs) {
      notify("No document management permission", "warn");
      return;
    }
    try {
      const res = await appApi.documentReindex(item.filename, item.source);
      setUploadInfo(
        `${item.filename}: docs=${res.loaded_documents || 0}, chunks=${res.chunks_indexed || 0}, triplets=${res.triplets_written || 0}`,
      );
      notify(`${item.filename} reindexed`, "success");
      await refreshDocuments();
    } catch (e) {
      await handleApiError(e, "Failed to reindex document");
    }
  };

  const refreshPrompts = async (silent = false) => {
    if (!silent) setPromptsLoading(true);
    try {
      const rows = await appApi.prompts();
      setPrompts(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, "Failed to load prompt templates");
    } finally {
      if (!silent) setPromptsLoading(false);
    }
  };

  const savePrompt = async () => {
    const title = promptTitle.trim();
    const content = promptContent.trim();
    if (!title || !content) {
      notify("Title and content are required", "warn");
      return;
    }
    try {
      const saved = editingPromptId
        ? await appApi.promptUpdate(editingPromptId, title, content)
        : await appApi.promptCreate(title, content);
      if (saved.agent_class) setAgentClassHint((saved.agent_class as AgentClassHint) || "");
      setEditingPromptId(null);
      setPromptTitle("");
      setPromptContent("");
      notify("Prompt saved", "success");
      await refreshPrompts();
    } catch (e) {
      await handleApiError(e, "Failed to save prompt");
    }
  };

  const checkPrompt = async () => {
    const title = promptTitle.trim();
    const content = promptContent.trim();
    if (!title || !content) {
      notify("Fill in title and content first", "warn");
      return;
    }
    try {
      setPromptCheckInfo("Checking...");
      const res = await appApi.promptCheck(title, content, useReasoning);
      const suggestions = (res.suggestions || []).filter(Boolean);
      const suggestionBlock = suggestions.length
        ? `\n\n[Suggestions]\n${suggestions.map((x, i) => `${i + 1}. ${x}`).join("\n")}`
        : "";
      setPromptTitle(res.title || title);
      setPromptContent(`${(res.content || content).trim()}${suggestionBlock}`);
      setPromptCheckInfo(`Check done. ${(res.issues || []).slice(0, 3).join(";")}`);
      notify("Prompt check completed", "success");
    } catch (e) {
      setPromptCheckInfo("");
      await handleApiError(e, "Failed to check prompt");
    }
  };

  const deletePrompt = async (item: PromptTemplate) => {
    if (!window.confirm(`Delete template: ${item.title}?`)) return;
    try {
      await appApi.promptDelete(item.prompt_id);
      if (editingPromptId === item.prompt_id) {
        setEditingPromptId(null);
        setPromptTitle("");
        setPromptContent("");
      }
      notify("Prompt deleted", "success");
      await refreshPrompts();
    } catch (e) {
      await handleApiError(e, "Failed to delete prompt");
    }
  };

  const editMessage = async (msg: SessionMessage) => {
    if (!currentSessionId) return;
    const next = window.prompt("Edit message content", msg.content || "");
    if (next === null) return;
    try {
      const rerun = msg.role === "user";
      if (rerun) setRunStatus("Re-running");
      const detail = await appApi.messageUpdate(
        currentSessionId,
        msg.message_id,
        next,
        rerun,
        useWeb,
        useReasoning,
      );
      setMessages(detail.messages || []);
      await refreshSessions();
      notify("Message updated", "success");
    } catch (e) {
      await handleApiError(e, "Failed to update message");
    } finally {
      setRunStatus("");
    }
  };

  const removeMessage = async (msg: SessionMessage) => {
    if (!currentSessionId) return;
    if (!window.confirm("Delete this message?")) return;
    try {
      const detail = await appApi.messageDelete(currentSessionId, msg.message_id);
      setMessages(detail.messages || []);
      await refreshSessions();
      notify("Message deleted", "success");
    } catch (e) {
      await handleApiError(e, "Failed to delete message");
    }
  };

  const ensureSessionForAsk = async () => {
    if (currentSessionId) return currentSessionId;
    return createSession();
  };

  const ask = async () => {
    const q = question.trim();
    if (!q || isSending) return;
    const sid = await ensureSessionForAsk();
    if (!sid) return;

    setIsSending(true);
    setQuestion("");
    setRunStatus("Processing");
    setMessages((prev) => [
      ...prev,
      { message_id: `local-user-${Date.now()}`, role: "user", content: q },
      { message_id: "local-assistant-stream", role: "assistant", content: "", metadata: { ...EMPTY_METADATA } },
    ]);

    try {
      const runStartedAt = performance.now();
      const elapsedMs = () => Math.max(1, Math.round(performance.now() - runStartedAt));
      const res = await appApi.streamQuery({
        question: q,
        useWebFallback: useWeb,
        useReasoning,
        sessionId: sid,
        agentClassHint: agentClassHint || undefined,
      });
      if (!res.ok || !res.body) {
        const raw = await res.text();
        let detail = "Stream request failed";
        if (raw) {
          try {
            const parsed = JSON.parse(raw);
            detail = String(parsed?.detail || raw);
          } catch {
            detail = raw;
          }
        }
        throw new Error(String(detail));
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let answer = "";
      let thoughts: string[] = [];
      let meta = { ...EMPTY_METADATA };
      let executionSteps = [...(EMPTY_METADATA.execution_steps || [])];
      let finalStreamMetadata = { ...EMPTY_METADATA };

      const pushExecutionStep = (kind: string, label: string, detail = "") => {
        const step = {
          kind,
          label,
          detail,
          at: new Date().toISOString(),
        };
        executionSteps = [...executionSteps, step].slice(-24);
        meta = {
          ...meta,
          current_status: label,
          execution_steps: executionSteps,
        };
      };

      const patchStreamMessage = (nextContent: string, nextMeta?: Partial<typeof meta>) => {
        if (nextMeta) meta = { ...meta, ...nextMeta };
        finalStreamMetadata = { ...meta, thoughts: thoughts.slice(-8) };
        setMessages((prev) =>
          prev.map((m) =>
            m.message_id === "local-assistant-stream"
              ? { ...m, content: nextContent, metadata: { ...meta, thoughts: thoughts.slice(-8) } }
              : m,
          ),
        );
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.split("\n").find((x) => x.startsWith("data: "));
          if (!line) continue;
          let evt: any;
          try {
            evt = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          if (evt.type === "status") {
            const nextStatus = mapRunStatus(evt.message || "");
            setRunStatus(nextStatus);
            if (nextStatus) pushExecutionStep("status", nextStatus, String(evt.message || ""));
            patchStreamMessage(answer, { current_status: nextStatus, execution_steps: executionSteps });
          } else if (evt.type === "route") {
            const routeLabel = `路由完成: ${evt.route || "unknown"}`;
            pushExecutionStep(
              "route",
              routeLabel,
              [evt.reason, evt.skill ? `skill=${evt.skill}` : "", evt.agent_class ? `agent=${evt.agent_class}` : ""]
                .filter(Boolean)
                .join(" | "),
            );
            patchStreamMessage(answer, {
              route: evt.route || "",
              agent_class: evt.agent_class || "",
              execution_steps: executionSteps,
              current_status: routeLabel,
            });
          }
          else if (evt.type === "thought") {
            if (evt.content) thoughts = [...thoughts, String(evt.content)];
            if (evt.content) pushExecutionStep("thought", "分析判断", String(evt.content));
            patchStreamMessage(answer, { execution_steps: executionSteps, current_status: meta.current_status });
          } else if (evt.type === "error") {
            const reason = String(evt.message || evt.error || "stream error");
            const cost = elapsedMs();
            pushExecutionStep("error", "执行失败", `${reason} | duration_ms=${cost}`);
            patchStreamMessage(answer, { execution_steps: executionSteps, current_status: "执行失败", latency_ms: cost });
            throw new Error(reason);
          } else if (evt.type === "vector_result") {
            const retrievedCount = Number(evt.retrieved_count || 0);
            pushExecutionStep("vector", "向量检索完成", `命中片段 ${retrievedCount} 条`);
            patchStreamMessage(answer, {
              execution_steps: executionSteps,
              current_status: "向量检索完成",
            });
          } else if (evt.type === "graph_result") {
            const entities = Array.isArray(evt.entities) ? evt.entities : [];
            pushExecutionStep("graph", "图谱检索完成", `命中实体 ${entities.length} 个`);
            patchStreamMessage(answer, {
              graph_entities: entities,
              execution_steps: executionSteps,
              current_status: "图谱检索完成",
            });
          } else if (evt.type === "web_result") {
            const webLabel = !!evt.used ? "联网补充完成" : "未触发联网补充";
            pushExecutionStep("web", webLabel, `web_used=${!!evt.used}`);
            patchStreamMessage(answer, {
              web_used: !!evt.used,
              execution_steps: executionSteps,
              current_status: webLabel,
            });
          }
          else if (evt.type === "answer_chunk") {
            answer += String(evt.content || "");
            patchStreamMessage(answer);
          } else if (evt.type === "answer_reset") {
            pushExecutionStep("rewrite", "答案已校正", "系统对流式答案做了一次重写或修正");
            answer = String(evt.content || "");
            patchStreamMessage(answer, { execution_steps: executionSteps, current_status: "答案已校正" });
          } else if (evt.type === "done") {
            const result = evt.result || {};
            const finalAnswer = String(result.answer || answer || "");
            answer = finalAnswer;
            const cost = elapsedMs();
            pushExecutionStep(
              "done",
              "执行完成",
              [
                result.route ? `route=${result.route}` : "",
                result.agent_class ? `agent=${result.agent_class}` : "",
                result.web_result ? `web=${!!result.web_result.used}` : "",
                `duration_ms=${cost}`,
              ]
                .filter(Boolean)
                .join(" | "),
            );
            patchStreamMessage(finalAnswer, {
              route: result.route || meta.route,
              agent_class: result.agent_class || meta.agent_class,
              web_used: !!(result.web_result && result.web_result.used),
              latency_ms: cost,
              thoughts: Array.isArray(result.thoughts) ? result.thoughts : thoughts,
              graph_entities: (result.graph_result && result.graph_result.entities) || meta.graph_entities || [],
              current_status: "执行完成",
              execution_steps: executionSteps,
              citations: [
                ...(((result.vector_result && result.vector_result.citations) || []) as Citation[]),
                ...(((result.web_result && result.web_result.citations) || []) as Citation[]),
              ],
            });
          }
        }
      }
      const detail = await appApi.sessionDetail(sid);
      setCurrentSessionId(detail.session_id);
      const nextMessages = [...(detail.messages || [])];
      for (let i = nextMessages.length - 1; i >= 0; i -= 1) {
        if (nextMessages[i]?.role !== "assistant") continue;
        nextMessages[i] = {
          ...nextMessages[i],
          metadata: {
            ...(nextMessages[i].metadata || {}),
            ...finalStreamMetadata,
          },
        };
        break;
      }
      setMessages(nextMessages);
      await refreshSessions();
    } catch (e) {
      const fallback = "Request failed. Please check backend/model status.";
      await handleApiError(e, fallback);
      const rawError = e instanceof Error && e.message ? e.message : fallback;
      const lowered = String(rawError).toLowerCase();
      const isNetworkDisconnect = (
        lowered.includes("networkerror") ||
        lowered.includes("failed to fetch") ||
        lowered.includes("network error")
      );
      let visibleError = isNetworkDisconnect
        ? "NetworkError: stream disconnected. Retrying with non-stream mode..."
        : rawError;
      if (isNetworkDisconnect && sid) {
        try {
          const fallbackRes = await appApi.query({
            question: q,
            useWebFallback: useWeb,
            useReasoning,
            sessionId: sid,
            agentClassHint: agentClassHint || undefined,
          });
          visibleError = String(fallbackRes.answer || "No answer returned");
        } catch {
          visibleError = "NetworkError: stream disconnected. Please verify backend(8000), Ollama(11434), then retry.";
        }
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.message_id === "local-assistant-stream"
            ? { ...m, content: visibleError }
            : m,
        ),
      );
    } finally {
      setIsSending(false);
      setRunStatus("");
    }
  };

  useEffect(() => {
    void (async () => {
      const rows = await refreshSessions();
      await refreshDocuments();
      await refreshPrompts();
      if (rows.length > 0) await loadSession(rows[0].session_id);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = questionRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(260, el.scrollHeight)}px`;
  }, [question]);

  useEffect(() => {
    if (chatScrollRef.current) chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshSessions(false, true);
      void refreshDocuments(true);
      void refreshPrompts(true);
    }, 25000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const preventDefault = (evt: DragEvent) => evt.preventDefault();
    window.addEventListener("dragover", preventDefault);
    window.addEventListener("drop", preventDefault);
    return () => {
      window.removeEventListener("dragover", preventDefault);
      window.removeEventListener("drop", preventDefault);
    };
  }, []);

  return (
    <div className="page-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand">RAG Operations Deck</div>
        <p className="muted">Frontend + Agent + PDF + Testing workspace.</p>
        <section className="panel">
          <div className="section-head">
            <strong>Sessions</strong>
            <button
              type="button"
              className="secondary tiny-btn"
              onClick={() => void createSession()}
              disabled={sessionLoading}
            >
              New
            </button>
          </div>
          {sessionLoading && <div className="skeleton-list" />}
          {!sessionLoading && sessions.length === 0 && <div className="muted">No sessions yet</div>}
          {!sessionLoading && sessions.length > 0 && (
            <ul className="list">
              {sessions.map((s) => (
                <li key={s.session_id} className={`session-item ${s.session_id === currentSessionId ? "active" : ""}`}>
                  <button
                    type="button"
                    className="list-main-btn"
                    onClick={() => void loadSession(s.session_id)}
                    disabled={busySessionId === s.session_id}
                  >
                    <span>{s.title || "Untitled"}</span>
                    <small>{s.message_count || 0} msgs</small>
                  </button>
                  <button type="button" className="danger tiny-btn" onClick={() => void deleteSession(s.session_id)}>
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <div className="section-head">
            <strong>Agent Workbench</strong>
            <small className="muted">current: {agentClassHint || "auto"}</small>
          </div>
          <div className="agent-mode-grid">
            {AGENT_MODES.map((mode) => (
              <button
                key={mode.title}
                type="button"
                className={`agent-mode-card ${agentClassHint === mode.key ? "active" : ""}`}
                onClick={() => switchAgentMode(mode.key)}
              >
                <strong>{mode.title}</strong>
                <span>{mode.desc}</span>
              </button>
            ))}
          </div>
          <div className="agent-stats">
            {agentDistribution.length === 0 && <span className="muted">No indexed docs yet</span>}
            {agentDistribution.map((item) => (
              <span key={item.agent} className="chip">
                {item.agent}: {item.count}
              </span>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="section-head">
            <strong>PDF Workbench</strong>
            <button type="button" className="secondary tiny-btn" onClick={draftPdfQuestion}>
              Draft Question
            </button>
          </div>
          <div className="pdf-kpi-grid">
            <div className="pdf-kpi-card">
              <span>PDF/Image Docs</span>
              <strong>{pdfDocuments.length}</strong>
            </div>
            <div className="pdf-kpi-card">
              <span>Need Reindex</span>
              <strong>{pdfNeedingReindex.length}</strong>
            </div>
          </div>
          <select
            value={pdfTargetFile}
            onChange={(e) => setPdfTargetFile(e.target.value)}
            disabled={!pdfDocuments.length}
          >
            {!pdfDocuments.length && <option value="">No PDF docs</option>}
            {pdfDocuments.map((doc) => (
              <option key={doc.source} value={doc.filename}>
                {doc.filename} (chunks={doc.chunks || 0})
              </option>
            ))}
          </select>
          <div className="row-actions wrap">
            <button type="button" className="secondary tiny-btn" onClick={() => switchAgentMode("pdf_text")}>
              Force pdf_text
            </button>
            <button type="button" className="secondary tiny-btn" onClick={() => switchAgentMode("")}>
              Back to auto
            </button>
          </div>
          {pdfNeedingReindex.length > 0 && (
            <div className="hint">Some PDF docs have 0 chunks. Reindex before asking detailed questions.</div>
          )}
        </section>

        <section className="panel">
          <div className="section-head">
            <strong>Documents</strong>
            <button type="button" className="secondary tiny-btn" onClick={() => void refreshDocuments()}>
              Refresh
            </button>
          </div>
          {canUploadAndManageDocs && (
            <div className="upload-box">
              {isAdmin && (
                <select
                  value={uploadVisibility}
                  onChange={(e) => setUploadVisibility((e.target.value as "private" | "public") || "private")}
                >
                  <option value="private">private</option>
                  <option value="public">public</option>
                </select>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={(evt) => void onMainUploadChange(evt)}
                accept=".md,.txt,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
              />
              <div className="muted">{uploading ? "Uploading..." : "Supports .md/.txt/.pdf/images"}</div>
              {uploadInfo && <div className="hint">{uploadInfo}</div>}
              {(uploading || uploadProgress > 0) && (
                <div className="progress-wrap">
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${Math.round(uploadProgress)}%` }} />
                  </div>
                  <div className="progress-text">{uploadProgressText || `Uploading ${Math.round(uploadProgress)}%`}</div>
                </div>
              )}
            </div>
          )}
          {canUploadAndManageDocs && (
            <div
              className={`dropzone ${docDropActive ? "dragover" : ""}`}
              onDragEnter={(evt) => {
                evt.preventDefault();
                evt.stopPropagation();
                setDocDropActive(true);
              }}
              onDragOver={(evt) => {
                evt.preventDefault();
                evt.stopPropagation();
                setDocDropActive(true);
              }}
              onDragLeave={(evt) => {
                evt.preventDefault();
                evt.stopPropagation();
                setDocDropActive(false);
              }}
              onDrop={(evt) => void onDocsDrop(evt)}
            >
              Drop docs here (.md / .txt / .pdf / images)
            </div>
          )}
          {docsLoading && <div className="skeleton-list" />}
          {!docsLoading && documents.length === 0 && <div className="muted">No indexed documents</div>}
          {!docsLoading && pdfDocuments.length > 0 && <div className="doc-subtitle">PDF/Image ({pdfDocuments.length})</div>}
          {!docsLoading &&
            pdfDocuments.map((doc) => (
              <div key={`${doc.filename}-${doc.source}`} className="doc-row">
                <div>
                  <div>{doc.filename}</div>
                  <small className="muted">
                    chunks={doc.chunks} | visibility={doc.visibility || "private"} | disk={doc.exists_on_disk ? "yes" : "no"} |
                    uploads={doc.in_uploads ? "yes" : "no"} | agent={doc.agent_class || "general"}
                  </small>
                </div>
                {(canUploadAndManageDocs && (isAdmin || doc.owner_user_id === user?.user_id)) && (
                  <div className="row-actions">
                    <button type="button" className="secondary tiny-btn" onClick={() => void reindexDocument(doc)}>
                      Reindex
                    </button>
                    <button type="button" className="danger tiny-btn" onClick={() => void deleteDocument(doc, false)}>
                      Del Index
                    </button>
                    <button type="button" className="danger tiny-btn" onClick={() => void deleteDocument(doc, true)}>
                      Del File
                    </button>
                  </div>
                )}
              </div>
            ))}
          {!docsLoading && nonPdfDocuments.length > 0 && <div className="doc-subtitle">Other Docs ({nonPdfDocuments.length})</div>}
          {!docsLoading &&
            nonPdfDocuments.map((doc) => (
              <div key={`${doc.filename}-${doc.source}`} className="doc-row">
                <div>
                  <div>{doc.filename}</div>
                  <small className="muted">
                    chunks={doc.chunks} | visibility={doc.visibility || "private"} | disk={doc.exists_on_disk ? "yes" : "no"} |
                    uploads={doc.in_uploads ? "yes" : "no"} | agent={doc.agent_class || "general"}
                  </small>
                </div>
                {(canUploadAndManageDocs && (isAdmin || doc.owner_user_id === user?.user_id)) && (
                  <div className="row-actions">
                    <button type="button" className="secondary tiny-btn" onClick={() => void reindexDocument(doc)}>
                      Reindex
                    </button>
                    <button type="button" className="danger tiny-btn" onClick={() => void deleteDocument(doc, false)}>
                      Del Index
                    </button>
                    <button type="button" className="danger tiny-btn" onClick={() => void deleteDocument(doc, true)}>
                      Del File
                    </button>
                  </div>
                )}
              </div>
            ))}
        </section>
        <section className="panel">
          <div className="section-head">
            <strong>Prompt Templates</strong>
            <button type="button" className="secondary tiny-btn" onClick={() => void refreshPrompts()}>
              Refresh
            </button>
          </div>
          <input value={promptTitle} onChange={(e) => setPromptTitle(e.target.value)} placeholder="Template title" />
          <textarea
            value={promptContent}
            onChange={(e) => setPromptContent(e.target.value)}
            placeholder="Write your prompt template..."
            rows={4}
          />
          <div className="row-actions">
            <button type="button" className="secondary tiny-btn" onClick={() => void checkPrompt()}>
              Check
            </button>
            <button type="button" className="tiny-btn" onClick={() => void savePrompt()}>
              {editingPromptId ? "Update" : "Save"}
            </button>
          </div>
          {promptCheckInfo && <div className="hint">{promptCheckInfo}</div>}
          {promptsLoading && <div className="skeleton-list" />}
          {!promptsLoading && prompts.length === 0 && <div className="muted">No templates yet</div>}
          {!promptsLoading &&
            prompts.map((p) => (
              <div key={p.prompt_id} className="prompt-row">
                <div>
                  <div>{p.title}</div>
                  <small className="muted">
                    agent={p.agent_class || "general"} | {(p.content || "").slice(0, 72)}
                  </small>
                </div>
                <div className="row-actions">
                  <button
                    type="button"
                    className="secondary tiny-btn"
                    onClick={() => {
                      setQuestion(p.content || "");
                      if (p.agent_class) setAgentClassHint((p.agent_class as AgentClassHint) || "");
                    }}
                  >
                    Use
                  </button>
                  <button
                    type="button"
                    className="secondary tiny-btn"
                    onClick={() => {
                      setEditingPromptId(p.prompt_id);
                      setPromptTitle(p.title || "");
                      setPromptContent(p.content || "");
                    }}
                  >
                    Edit
                  </button>
                  <button type="button" className="danger tiny-btn" onClick={() => void deletePrompt(p)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
        </section>
      </aside>

      <div className={`backdrop ${sidebarOpen ? "show" : ""}`} onClick={() => setSidebarOpen(false)} />
      <main className="main">
        <ChatTopbar
          userBadge={userBadge}
          themeLabel={themeLabel}
          isAdmin={isAdmin}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          onThemeToggle={onThemeToggle}
          onLogout={onLogout}
        />

        <ChatMessages
          messages={messages}
          containerRef={chatScrollRef}
          onEditMessage={editMessage}
          onRemoveMessage={removeMessage}
        />

        <ChatComposer
          composerDropActive={composerDropActive}
          question={question}
          questionRef={questionRef}
          chatUploadInputRef={chatUploadInputRef}
          isSending={isSending}
          quickPrompts={QUICK_PROMPTS}
          runStatus={runStatus}
          error={error}
          useWeb={useWeb}
          useReasoning={useReasoning}
          agentClassHint={agentClassHint}
          onQuestionChange={setQuestion}
          onAsk={ask}
          onClearQuestion={() => setQuestion("")}
          onPromptPick={setQuestion}
          onUseWebChange={setUseWeb}
          onUseReasoningChange={setUseReasoning}
          onAgentClassHintChange={(v) => setAgentClassHint((v as AgentClassHint) || "")}
          onComposerDragEnter={(evt) => {
            evt.preventDefault();
            evt.stopPropagation();
            setComposerDropActive(true);
          }}
          onComposerDragOver={(evt) => {
            evt.preventDefault();
            evt.stopPropagation();
            setComposerDropActive(true);
          }}
          onComposerDragLeave={(evt) => {
            evt.preventDefault();
            evt.stopPropagation();
            setComposerDropActive(false);
          }}
          onComposerDrop={onComposerDrop}
          onChatUploadChange={onChatUploadChange}
        />
      </main>

      <ToastStack toasts={toasts} />
    </div>
  );
}
