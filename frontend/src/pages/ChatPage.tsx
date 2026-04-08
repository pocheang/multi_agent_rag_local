import { isValidElement, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "react-router-dom";
import { ApiError, appApi } from "@/lib/api";
import type {
  AuthUser,
  Citation,
  IndexedFileSummary,
  PromptTemplate,
  SessionMessage,
  SessionSummary,
} from "@/types/api";

type Props = {
  user: AuthUser | null;
  onLogout: () => Promise<void>;
  themeLabel: string;
  onThemeToggle: () => void;
};

type Toast = {
  id: string;
  text: string;
  kind: "info" | "success" | "warn" | "error";
};

const QUICK_PROMPTS = [
  "分析这次告警可能的攻击链，并给出 P0/P1/P2 处置优先级",
  "针对暴露在公网的 Web 服务，给一份分层防护加固清单",
  "给出勒索事件的应急响应流程，包含证据保全和恢复步骤",
  "解释 SQL 注入的原理、常见检测信号和修复方案",
];

const SUPPORTED_DOC_RE = /\.(md|txt|pdf|png|jpe?g|bmp|tiff?|webp)$/i;
const SUPPORTED_CHAT_RE = /\.(pdf|png|jpe?g|bmp|tiff?|webp)$/i;

const EMPTY_METADATA = {
  route: "",
  agent_class: "",
  web_used: false,
  thoughts: [] as string[],
  graph_entities: [] as string[],
  citations: [] as Citation[],
};

function isMobile() {
  return window.matchMedia("(max-width: 1080px)").matches;
}

function mapRunStatus(statusKey: string) {
  const map: Record<string, string> = {
    routing: "路由中",
    retrieving_vector: "检索向量库",
    retrieving_graph: "检索图谱",
    retrieving_web: "联网补充",
    synthesizing: "生成回答",
    pdf_upload_required: "需要先上传文档",
    pdf_selection_required: "需要选择文档",
    pdf_reindex_required: "需要重建索引",
  };
  return map[statusKey] || statusKey || "";
}

function CodeBlock({ code, className = "" }: { code: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  };
  return (
    <pre>
      <button type="button" className="copy-code-btn" onClick={() => void copyCode()}>
        {copied ? "已复制" : "复制"}
      </button>
      <code className={className}>{code}</code>
    </pre>
  );
}

function MarkdownBlock({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        pre({ children }) {
          const child = Array.isArray(children) ? children[0] : children;
          if (!isValidElement(child)) return <pre>{children}</pre>;
          const className = String((child.props as { className?: string })?.className || "");
          const code = String((child.props as { children?: unknown })?.children || "").replace(/\n$/, "");
          return <CodeBlock className={className} code={code} />;
        },
      }}
    >
      {text || ""}
    </ReactMarkdown>
  );
}

export function ChatPage({ user, onLogout, themeLabel, onThemeToggle }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [runStatus, setRunStatus] = useState("");
  const [useWeb, setUseWeb] = useState(true);
  const [useReasoning, setUseReasoning] = useState(true);

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

  const notify = (text: string, kind: Toast["kind"] = "info", ttl = 2400) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev, { id, text, kind }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), ttl);
  };

  const closeSidebar = () => {
    if (isMobile()) setSidebarOpen(false);
  };

  const handleApiError = async (e: unknown, fallback: string) => {
    if (e instanceof ApiError && e.status === 401) {
      notify("登录状态失效，请重新登录", "error");
      await onLogout();
      return;
    }
    const msg = e instanceof Error ? e.message : fallback;
    setError(msg);
    notify(msg, "error");
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
      await handleApiError(e, "读取会话失败");
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
      await handleApiError(e, "会话加载失败");
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
      notify("已创建新会话", "success");
      closeSidebar();
      return detail.session_id;
    } catch (e) {
      await handleApiError(e, "创建会话失败");
      return null;
    }
  };

  const deleteSession = async (sessionId: string) => {
    if (!window.confirm("确认删除这个会话吗？")) return;
    try {
      await appApi.sessionDelete(sessionId);
      if (sessionId === currentSessionId) {
        setCurrentSessionId(null);
        setMessages([]);
      }
      await refreshSessions();
      notify("会话已删除", "success");
    } catch (e) {
      await handleApiError(e, "删除会话失败");
    }
  };

  const refreshDocuments = async (silent = false) => {
    if (!silent) setDocsLoading(true);
    try {
      const rows = await appApi.documents();
      setDocuments(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, "文档加载失败");
    } finally {
      if (!silent) setDocsLoading(false);
    }
  };

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return;
    if (!canUploadAndManageDocs) {
      notify("当前角色无上传权限", "warn");
      return;
    }
    try {
      setUploading(true);
      setUploadProgress(0);
      setUploadProgressText("上传准备中...");
      setUploadInfo("上传中...");
      const data = await appApi.upload(
        files,
        (percent) => {
          setUploadProgress(percent);
          setUploadProgressText(`上传中 ${Math.round(percent)}%`);
        },
        uploadVisibility,
      );
      setUploadProgress(100);
      setUploadProgressText("上传完成");
      setUploadInfo(
        `已入库: ${data.filenames.join(", ")} | 跳过: ${(data.skipped_files || []).join(", ") || "无"} | 可见性: ${data.visibility_applied || uploadVisibility} | docs=${data.loaded_documents}, chunks=${data.chunks_indexed}, triplets=${data.triplets_written}`,
      );
      notify(`上传完成: ${data.filenames.join(", ")}`, "success");
      await refreshDocuments();
    } catch (e) {
      setUploadInfo(`上传失败: ${e instanceof Error ? e.message : "unknown error"}`);
      await handleApiError(e, "上传失败");
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
      notify("这里只支持 PDF/图片文件", "warn");
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
      notify("仅支持 .md / .txt / .pdf / 图片文件", "warn");
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
      notify("这里只支持 PDF/图片文件", "warn");
      return;
    }
    await uploadFiles(files);
  };

  const deleteDocument = async (item: IndexedFileSummary, removeFile: boolean) => {
    if (!canUploadAndManageDocs) {
      notify("当前角色无文档管理权限", "warn");
      return;
    }
    const verb = removeFile ? "删除文件和索引" : "删除索引";
    if (!window.confirm(`${verb}: ${item.filename} ?`)) return;
    try {
      const res = await appApi.documentDelete(item.filename, item.source, removeFile);
      setUploadInfo(
        `${item.filename}: chunks_removed=${res.chunks_removed}, triplets_removed=${res.triplets_removed}, file_removed=${res.file_removed}`,
      );
      notify(`${item.filename} 删除成功`, "success");
      await refreshDocuments();
    } catch (e) {
      await handleApiError(e, "文档删除失败");
    }
  };

  const reindexDocument = async (item: IndexedFileSummary) => {
    if (!canUploadAndManageDocs) {
      notify("当前角色无文档管理权限", "warn");
      return;
    }
    try {
      const res = await appApi.documentReindex(item.filename, item.source);
      setUploadInfo(
        `${item.filename}: docs=${res.loaded_documents || 0}, chunks=${res.chunks_indexed || 0}, triplets=${res.triplets_written || 0}`,
      );
      notify(`${item.filename} 重建索引完成`, "success");
      await refreshDocuments();
    } catch (e) {
      await handleApiError(e, "文档重建失败");
    }
  };

  const refreshPrompts = async (silent = false) => {
    if (!silent) setPromptsLoading(true);
    try {
      const rows = await appApi.prompts();
      setPrompts(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, "Prompt 模板加载失败");
    } finally {
      if (!silent) setPromptsLoading(false);
    }
  };

  const savePrompt = async () => {
    const title = promptTitle.trim();
    const content = promptContent.trim();
    if (!title || !content) {
      notify("请填写模板标题和内容", "warn");
      return;
    }
    try {
      if (editingPromptId) await appApi.promptUpdate(editingPromptId, title, content);
      else await appApi.promptCreate(title, content);
      setEditingPromptId(null);
      setPromptTitle("");
      setPromptContent("");
      notify("模板已保存", "success");
      await refreshPrompts();
    } catch (e) {
      await handleApiError(e, "模板保存失败");
    }
  };

  const checkPrompt = async () => {
    const title = promptTitle.trim();
    const content = promptContent.trim();
    if (!title || !content) {
      notify("请先填写模板标题和内容", "warn");
      return;
    }
    try {
      setPromptCheckInfo("检查中...");
      const res = await appApi.promptCheck(title, content, useReasoning);
      const suggestions = (res.suggestions || []).filter(Boolean);
      const suggestionBlock = suggestions.length
        ? `\n\n【建议补充（可自行修改）】\n${suggestions.map((x, i) => `${i + 1}. ${x}`).join("\n")}`
        : "";
      setPromptTitle(res.title || title);
      setPromptContent(`${(res.content || content).trim()}${suggestionBlock}`);
      setPromptCheckInfo(`检查完成。${(res.issues || []).slice(0, 3).join("；")}`);
      notify("模板检查完成", "success");
    } catch (e) {
      setPromptCheckInfo("");
      await handleApiError(e, "模板检查失败");
    }
  };

  const deletePrompt = async (item: PromptTemplate) => {
    if (!window.confirm(`删除模板：${item.title} ?`)) return;
    try {
      await appApi.promptDelete(item.prompt_id);
      if (editingPromptId === item.prompt_id) {
        setEditingPromptId(null);
        setPromptTitle("");
        setPromptContent("");
      }
      notify("模板已删除", "success");
      await refreshPrompts();
    } catch (e) {
      await handleApiError(e, "模板删除失败");
    }
  };

  const editMessage = async (msg: SessionMessage) => {
    if (!currentSessionId) return;
    const next = window.prompt("修改消息内容", msg.content || "");
    if (next === null) return;
    try {
      const rerun = msg.role === "user";
      if (rerun) setRunStatus("重跑中");
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
      notify("消息已更新", "success");
    } catch (e) {
      await handleApiError(e, "消息更新失败");
    } finally {
      setRunStatus("");
    }
  };

  const removeMessage = async (msg: SessionMessage) => {
    if (!currentSessionId) return;
    if (!window.confirm("确认删除这条消息吗？")) return;
    try {
      const detail = await appApi.messageDelete(currentSessionId, msg.message_id);
      setMessages(detail.messages || []);
      await refreshSessions();
      notify("消息已删除", "success");
    } catch (e) {
      await handleApiError(e, "消息删除失败");
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
    setRunStatus("运行中");
    setMessages((prev) => [
      ...prev,
      { message_id: `local-user-${Date.now()}`, role: "user", content: q },
      { message_id: "local-assistant-stream", role: "assistant", content: "", metadata: { ...EMPTY_METADATA } },
    ]);

    try {
      const res = await appApi.streamQuery({ question: q, useWebFallback: useWeb, useReasoning, sessionId: sid });
      if (!res.ok || !res.body) {
        const raw = await res.text();
        const detail = raw ? JSON.parse(raw).detail || raw : "stream failed";
        throw new Error(String(detail));
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let answer = "";
      let thoughts: string[] = [];
      let meta = { ...EMPTY_METADATA };

      const patchStreamMessage = (nextContent: string, nextMeta?: Partial<typeof meta>) => {
        if (nextMeta) meta = { ...meta, ...nextMeta };
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
          const evt = JSON.parse(line.slice(6));
          if (evt.type === "status") setRunStatus(mapRunStatus(evt.message || ""));
          else if (evt.type === "route") patchStreamMessage(answer, { route: evt.route || "", agent_class: evt.agent_class || "" });
          else if (evt.type === "thought") {
            if (evt.content) thoughts = [...thoughts, String(evt.content)];
            patchStreamMessage(answer);
          } else if (evt.type === "graph_result") patchStreamMessage(answer, { graph_entities: Array.isArray(evt.entities) ? evt.entities : [] });
          else if (evt.type === "web_result") patchStreamMessage(answer, { web_used: !!evt.used });
          else if (evt.type === "answer_chunk") {
            answer += String(evt.content || "");
            patchStreamMessage(answer);
          } else if (evt.type === "done") {
            const result = evt.result || {};
            patchStreamMessage(answer || String(result.answer || ""), {
              route: result.route || meta.route,
              agent_class: result.agent_class || meta.agent_class,
              web_used: !!(result.web_result && result.web_result.used),
              thoughts: Array.isArray(result.thoughts) ? result.thoughts : thoughts,
              graph_entities: (result.graph_result && result.graph_result.entities) || meta.graph_entities || [],
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
      setMessages(detail.messages || []);
      await refreshSessions();
    } catch (e) {
      await handleApiError(e, "请求失败，请确认后端与模型服务状态");
      setMessages((prev) =>
        prev.map((m) =>
          m.message_id === "local-assistant-stream"
            ? { ...m, content: "请求失败。请确认 API 已启动、模型已就绪、向量库已导入。" }
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
        <div className="brand">CyberSec RAG</div>
        <p className="muted">React 全功能迁移版（进行中）</p>
        <section className="panel">
          <div className="section-head">
            <strong>事件会话</strong>
            <button type="button" className="secondary tiny-btn" onClick={() => void createSession()} disabled={sessionLoading}>新建</button>
          </div>
          {sessionLoading && <div className="skeleton-list" />}
          {!sessionLoading && sessions.length === 0 && <div className="muted">暂无会话</div>}
          {!sessionLoading && sessions.length > 0 && (
            <ul className="list">
              {sessions.map((s) => (
                <li key={s.session_id} className={`session-item ${s.session_id === currentSessionId ? "active" : ""}`}>
                  <button type="button" className="list-main-btn" onClick={() => void loadSession(s.session_id)} disabled={busySessionId === s.session_id}>
                    <span>{s.title || "新会话"}</span>
                    <small>{s.message_count || 0} 条</small>
                  </button>
                  <button type="button" className="danger tiny-btn" onClick={() => void deleteSession(s.session_id)}>删除</button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="panel">
          <div className="section-head">
            <strong>文档库</strong>
            <button type="button" className="secondary tiny-btn" onClick={() => void refreshDocuments()}>刷新</button>
          </div>
          {canUploadAndManageDocs && (
            <div className="upload-box">
              {isAdmin && (
                <select
                  value={uploadVisibility}
                  onChange={(e) => setUploadVisibility((e.target.value as "private" | "public") || "private")}
                >
                  <option value="private">仅自己可见</option>
                  <option value="public">所有人可见</option>
                </select>
              )}
              <input ref={fileInputRef} type="file" multiple onChange={onMainUploadChange} accept=".md,.txt,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp" />
              <div className="muted">{uploading ? "上传中..." : "支持 .md/.txt/.pdf/图片"}</div>
              {uploadInfo && <div className="hint">{uploadInfo}</div>}
              {(uploading || uploadProgress > 0) && (
                <div className="progress-wrap">
                  <div className="progress-bar"><div className="progress-fill" style={{ width: `${Math.round(uploadProgress)}%` }} /></div>
                  <div className="progress-text">{uploadProgressText || `上传中 ${Math.round(uploadProgress)}%`}</div>
                </div>
              )}
            </div>
          )}
          {canUploadAndManageDocs && (
            <div
              className={`dropzone ${docDropActive ? "dragover" : ""}`}
              onDragEnter={(evt) => { evt.preventDefault(); evt.stopPropagation(); setDocDropActive(true); }}
              onDragOver={(evt) => { evt.preventDefault(); evt.stopPropagation(); setDocDropActive(true); }}
              onDragLeave={(evt) => { evt.preventDefault(); evt.stopPropagation(); setDocDropActive(false); }}
              onDrop={(evt) => void onDocsDrop(evt)}
            >
              拖拽文件到这里上传（.md / .txt / .pdf / 图片）
            </div>
          )}
          {docsLoading && <div className="skeleton-list" />}
          {!docsLoading && documents.length === 0 && <div className="muted">暂无已索引文件</div>}
          {!docsLoading && documents.map((doc) => (
            <div key={`${doc.filename}-${doc.source}`} className="doc-row">
              <div>
                <div>{doc.filename}</div>
                <small className="muted">
                  chunks={doc.chunks} | visibility={doc.visibility || "private"} | on_disk={doc.exists_on_disk ? "yes" : "no"} | uploads={doc.in_uploads ? "yes" : "no"}
                </small>
              </div>
              {(canUploadAndManageDocs && (isAdmin || doc.owner_user_id === user?.user_id)) && (
                <div className="row-actions">
                  <button type="button" className="secondary tiny-btn" onClick={() => void reindexDocument(doc)}>重建</button>
                  <button type="button" className="danger tiny-btn" onClick={() => void deleteDocument(doc, false)}>删索引</button>
                  <button type="button" className="danger tiny-btn" onClick={() => void deleteDocument(doc, true)}>删文件</button>
                </div>
              )}
            </div>
          ))}
        </section>
        <section className="panel">
          <div className="section-head">
            <strong>Prompt 模板库</strong>
            <button type="button" className="secondary tiny-btn" onClick={() => void refreshPrompts()}>刷新</button>
          </div>
          <input value={promptTitle} onChange={(e) => setPromptTitle(e.target.value)} placeholder="模板标题" />
          <textarea value={promptContent} onChange={(e) => setPromptContent(e.target.value)} placeholder="在这里写模板内容..." rows={4} />
          <div className="row-actions">
            <button type="button" className="secondary tiny-btn" onClick={() => void checkPrompt()}>检查并补全</button>
            <button type="button" className="tiny-btn" onClick={() => void savePrompt()}>{editingPromptId ? "更新模板" : "保存模板"}</button>
          </div>
          {promptCheckInfo && <div className="hint">{promptCheckInfo}</div>}
          {promptsLoading && <div className="skeleton-list" />}
          {!promptsLoading && prompts.length === 0 && <div className="muted">还没有模板</div>}
          {!promptsLoading && prompts.map((p) => (
            <div key={p.prompt_id} className="prompt-row">
              <div><div>{p.title}</div><small className="muted">{(p.content || "").slice(0, 86)}</small></div>
              <div className="row-actions">
                <button type="button" className="secondary tiny-btn" onClick={() => setQuestion(p.content || "")}>使用</button>
                <button type="button" className="secondary tiny-btn" onClick={() => { setEditingPromptId(p.prompt_id); setPromptTitle(p.title || ""); setPromptContent(p.content || ""); }}>编辑</button>
                <button type="button" className="danger tiny-btn" onClick={() => void deletePrompt(p)}>删除</button>
              </div>
            </div>
          ))}
        </section>
      </aside>

      <div className={`backdrop ${sidebarOpen ? "show" : ""}`} onClick={() => setSidebarOpen(false)} />
      <main className="main">
        <header className="topbar">
          <div>
            <h2>网络安全攻防问答中枢（React）</h2>
            <p className="muted">已迁移: 会话、流式问答、文档上传、Prompt 模板、RBAC。</p>
          </div>
          <div className="top-actions">
            <span className="user-badge">{userBadge}</span>
            <button type="button" className="secondary" onClick={() => setSidebarOpen((v) => !v)}>菜单</button>
            <button type="button" className="secondary" onClick={onThemeToggle}>{themeLabel}</button>
            <Link className="secondary link-btn" to="/app/architecture">架构总览</Link>
            <label className="checkline"><input type="checkbox" checked={useWeb} onChange={(e) => setUseWeb(e.target.checked)} />联网校验</label>
            <label className="checkline"><input type="checkbox" checked={useReasoning} onChange={(e) => setUseReasoning(e.target.checked)} />推理模型</label>
            {isAdmin && <Link className="secondary link-btn" to="/app/admin">管理页</Link>}
            <button type="button" onClick={() => void onLogout()}>退出</button>
          </div>
        </header>
        <section className="chat-window panel" ref={chatScrollRef}>
          {messages.length === 0 && <div className="muted">还没有消息，输入一个问题开始分析。</div>}
          {messages.map((msg) => {
            const isAssistant = msg.role === "assistant";
            const md = msg.metadata || EMPTY_METADATA;
            return (
              <article key={msg.message_id} className={`bubble ${isAssistant ? "assistant" : "user"}`}>
                <div className="message-head">
                  <span>{isAssistant ? "助手" : "用户"}</span>
                  {msg.message_id.startsWith("local-") ? null : (
                    <div className="row-actions">
                      <button type="button" className="secondary tiny-btn" onClick={() => void editMessage(msg)}>修改</button>
                      <button type="button" className="danger tiny-btn" onClick={() => void removeMessage(msg)}>删除</button>
                    </div>
                  )}
                </div>
                <div className="markdown"><MarkdownBlock text={msg.content || ""} /></div>
                {isAssistant && (
                  <>
                    <div className="chips">
                      {md.route && <span className="chip">route: {md.route}</span>}
                      {md.agent_class && <span className="chip">agent: {md.agent_class}</span>}
                      <span className="chip">web: {md.web_used ? "yes" : "no"}</span>
                      {(md.graph_entities || []).slice(0, 6).map((x) => <span key={x} className="chip">{x}</span>)}
                    </div>
                    {(md.thoughts || []).length > 0 && (
                      <details>
                        <summary>查看过程</summary>
                        <ul className="compact-list">{(md.thoughts || []).slice(-8).map((x, i) => <li key={`${msg.message_id}-thought-${i}`}>{x}</li>)}</ul>
                      </details>
                    )}
                    {(md.citations || []).length > 0 && (
                      <details>
                        <summary>查看引用</summary>
                        <div className="citation-grid">
                          {(md.citations || []).slice(0, 8).map((c, i) => (
                            <div key={`${msg.message_id}-cit-${i}`} className="citation-card">
                              <strong>{c.source || "unknown"}</strong>
                              <MarkdownBlock text={c.content || ""} />
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </>
                )}
              </article>
            );
          })}
        </section>
        <section
          className={`panel composer-panel ${composerDropActive ? "dragover" : ""}`}
          onDragEnter={(evt) => { evt.preventDefault(); evt.stopPropagation(); setComposerDropActive(true); }}
          onDragOver={(evt) => { evt.preventDefault(); evt.stopPropagation(); setComposerDropActive(true); }}
          onDragLeave={(evt) => { evt.preventDefault(); evt.stopPropagation(); setComposerDropActive(false); }}
          onDrop={(evt) => void onComposerDrop(evt)}
        >
          <textarea
            ref={questionRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="输入安全问题，例如：如何检测疑似横向移动？Ctrl/⌘ + Enter 发送"
            rows={3}
            onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); void ask(); } }}
          />
          <div className="row-actions">
            <button type="button" onClick={() => void ask()} disabled={isSending}>{isSending ? "分析中..." : "分析"}</button>
            <label className="secondary link-btn">
              上传 PDF/图片
              <input ref={chatUploadInputRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp" style={{ display: "none" }} onChange={onChatUploadChange} />
            </label>
            <button type="button" className="secondary" onClick={() => setQuestion("")}>清空</button>
          </div>
          <div className="row-actions wrap">{QUICK_PROMPTS.map((x) => <button key={x} type="button" className="secondary tiny-btn" onClick={() => setQuestion(x)}>{x}</button>)}</div>
          {runStatus && <div className="status">{runStatus}</div>}
          {error && <div className="status error">{error}</div>}
        </section>
      </main>
      <div className="toast-stack">{toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}</div>
    </div>
  );
}
