import { useEffect, useRef, useState } from "react";
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
  const [agentClassHint, setAgentClassHint] = useState<AgentClassHint>("");

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
      notify("登录已过期，请重新登录", "error");
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
      await handleApiError(e, "加载会话失败");
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
      await handleApiError(e, "刷新会话列表失败");
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
      notify("新会话已创建", "success");
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
      await handleApiError(e, "加载文档失败");
    } finally {
      if (!silent) setDocsLoading(false);
    }
  };

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return;
    if (!canUploadAndManageDocs) {
      notify("无上传权限", "warn");
      return;
    }
    try {
      setUploading(true);
      setUploadProgress(0);
      setUploadProgressText("准备上传...");
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
        `已索引: ${data.filenames.join(", ")} | 跳过: ${(data.skipped_files || []).join(", ") || "无"} | 可见性: ${data.visibility_applied || uploadVisibility} | 文档=${data.loaded_documents}, 分块=${data.chunks_indexed}, 三元组=${data.triplets_written}`,
      );
      const classes = Object.values(data.assigned_agent_classes || {}).filter(Boolean);
      if (classes.length > 0) {
        const unique = Array.from(new Set(classes));
        if (unique.length === 1) setAgentClassHint((unique[0] as AgentClassHint) || "");
      }
      notify(`上传完成: ${data.filenames.join(", ")}`, "success");
      await refreshDocuments();
    } catch (e) {
      setUploadInfo(`上传失败: ${e instanceof Error ? e.message : "未知错误"}`);
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
      notify("只支持 .md / .txt / .pdf / 图片 文件", "warn");
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
      notify("无文档管理权限", "warn");
      return;
    }
    const verb = removeFile ? "删除文件和索引" : "删除索引";
    if (!window.confirm(`${verb}: ${item.filename} ?`)) return;
    try {
      const res = await appApi.documentDelete(item.filename, item.source, removeFile);
      setUploadInfo(
        `${item.filename}: 已删分块=${res.chunks_removed}, 已删三元组=${res.triplets_removed}, 文件已删=${res.file_removed}`,
      );
      notify(`${item.filename} 已删除`, "success");
      await refreshDocuments();
    } catch (e) {
      await handleApiError(e, "删除文档失败");
    }
  };

  const reindexDocument = async (item: IndexedFileSummary) => {
    if (!canUploadAndManageDocs) {
      notify("无文档管理权限", "warn");
      return;
    }
    try {
      const res = await appApi.documentReindex(item.filename, item.source);
      setUploadInfo(
        `${item.filename}: 文档=${res.loaded_documents || 0}, 分块=${res.chunks_indexed || 0}, 三元组=${res.triplets_written || 0}`,
      );
      notify(`${item.filename} 已重建索引`, "success");
      await refreshDocuments();
    } catch (e) {
      await handleApiError(e, "重建索引失败");
    }
  };

  const refreshPrompts = async (silent = false) => {
    if (!silent) setPromptsLoading(true);
    try {
      const rows = await appApi.prompts();
      setPrompts(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, "加载提示词模板失败");
    } finally {
      if (!silent) setPromptsLoading(false);
    }
  };

  const savePrompt = async () => {
    const title = promptTitle.trim();
    const content = promptContent.trim();
    if (!title || !content) {
      notify("请填写标题和内容", "warn");
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
      notify("提示词已保存", "success");
      await refreshPrompts();
    } catch (e) {
      await handleApiError(e, "保存提示词失败");
    }
  };

  const checkPrompt = async () => {
    const title = promptTitle.trim();
    const content = promptContent.trim();
    if (!title || !content) {
      notify("请先填写标题和内容", "warn");
      return;
    }
    try {
      setPromptCheckInfo("检查中...");
      const res = await appApi.promptCheck(title, content, useReasoning);
      const suggestions = (res.suggestions || []).filter(Boolean);
      const suggestionBlock = suggestions.length
        ? `\n\n[建议补充]\n${suggestions.map((x, i) => `${i + 1}. ${x}`).join("\n")}`
        : "";
      setPromptTitle(res.title || title);
      setPromptContent(`${(res.content || content).trim()}${suggestionBlock}`);
      setPromptCheckInfo(`检查完成。${(res.issues || []).slice(0, 3).join("；")}`);
      notify("提示词检查完成", "success");
    } catch (e) {
      setPromptCheckInfo("");
      await handleApiError(e, "检查提示词失败");
    }
  };

  const deletePrompt = async (item: PromptTemplate) => {
    if (!window.confirm(`确认删除模板：${item.title} ？`)) return;
    try {
      await appApi.promptDelete(item.prompt_id);
      if (editingPromptId === item.prompt_id) {
        setEditingPromptId(null);
        setPromptTitle("");
        setPromptContent("");
      }
      notify("提示词已删除", "success");
      await refreshPrompts();
    } catch (e) {
      await handleApiError(e, "删除提示词失败");
    }
  };

  const editMessage = async (msg: SessionMessage) => {
    if (!currentSessionId) return;
    const next = window.prompt("编辑消息内容", msg.content || "");
    if (next === null) return;
    try {
      const rerun = msg.role === "user";
      if (rerun) setRunStatus("重新执行中");
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
      await handleApiError(e, "更新消息失败");
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
      await handleApiError(e, "删除消息失败");
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
    setRunStatus("处理中");
    setMessages((prev) => [
      ...prev,
      { message_id: `local-user-${Date.now()}`, role: "user", content: q },
      { message_id: "local-assistant-stream", role: "assistant", content: "", metadata: { ...EMPTY_METADATA } },
    ]);

    try {
      const res = await appApi.streamQuery({
        question: q,
        useWebFallback: useWeb,
        useReasoning,
        sessionId: sid,
        agentClassHint: agentClassHint || undefined,
      });
      if (!res.ok || !res.body) {
        const raw = await res.text();
        const detail = raw ? JSON.parse(raw).detail || raw : "流式请求失败";
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
          } else if (evt.type === "answer_reset") {
            answer = String(evt.content || "");
            patchStreamMessage(answer);
          } else if (evt.type === "done") {
            const result = evt.result || {};
            const finalAnswer = String(result.answer || answer || "");
            answer = finalAnswer;
            patchStreamMessage(finalAnswer, {
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
      await handleApiError(e, "请求失败，请检查后端或模型状态");
      setMessages((prev) =>
        prev.map((m) =>
          m.message_id === "local-assistant-stream"
            ? { ...m, content: "请求失败，请检查 API、模型服务和向量索引状态。" }
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
        <p className="muted">React 全功能迁移版</p>
        <section className="panel">
          <div className="section-head">
            <strong>会话</strong>
            <button
              type="button"
              className="secondary tiny-btn"
              onClick={() => void createSession()}
              disabled={sessionLoading}
            >
              新建
            </button>
          </div>
          {sessionLoading && <div className="skeleton-list" />}
          {!sessionLoading && sessions.length === 0 && <div className="muted">暂无会话</div>}
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
                    <span>{s.title || "新会话"}</span>
                    <small>{s.message_count || 0} 条消息</small>
                  </button>
                  <button type="button" className="danger tiny-btn" onClick={() => void deleteSession(s.session_id)}>
                    删除
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="panel">
          <div className="section-head">
            <strong>文档</strong>
            <button type="button" className="secondary tiny-btn" onClick={() => void refreshDocuments()}>
              刷新
            </button>
          </div>
          {canUploadAndManageDocs && (
            <div className="upload-box">
              {isAdmin && (
                <select
                  value={uploadVisibility}
                  onChange={(e) => setUploadVisibility((e.target.value as "private" | "public") || "private")}
                >
                  <option value="private">私有</option>
                  <option value="public">公开</option>
                </select>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={(evt) => void onMainUploadChange(evt)}
                accept=".md,.txt,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
              />
              <div className="muted">{uploading ? "上传中..." : "支持 .md/.txt/.pdf/图片"}</div>
              {uploadInfo && <div className="hint">{uploadInfo}</div>}
              {(uploading || uploadProgress > 0) && (
                <div className="progress-wrap">
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${Math.round(uploadProgress)}%` }} />
                  </div>
                  <div className="progress-text">{uploadProgressText || `上传中 ${Math.round(uploadProgress)}%`}</div>
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
              拖拽文件到这里（.md / .txt / .pdf / 图片）
            </div>
          )}
          {docsLoading && <div className="skeleton-list" />}
          {!docsLoading && documents.length === 0 && <div className="muted">暂无已索引文档</div>}
          {!docsLoading &&
            documents.map((doc) => (
              <div key={`${doc.filename}-${doc.source}`} className="doc-row">
                <div>
                  <div>{doc.filename}</div>
                  <small className="muted">
                    分块={doc.chunks} | 可见性={doc.visibility || "private"} | 在磁盘={doc.exists_on_disk ? "是" : "否"} |
                    上传目录={doc.in_uploads ? "是" : "否"} | agent={doc.agent_class || "general"}
                  </small>
                </div>
                {(canUploadAndManageDocs && (isAdmin || doc.owner_user_id === user?.user_id)) && (
                  <div className="row-actions">
                    <button type="button" className="secondary tiny-btn" onClick={() => void reindexDocument(doc)}>
                      重建索引
                    </button>
                    <button type="button" className="danger tiny-btn" onClick={() => void deleteDocument(doc, false)}>
                      删除索引
                    </button>
                    <button type="button" className="danger tiny-btn" onClick={() => void deleteDocument(doc, true)}>
                      删除文件
                    </button>
                  </div>
                )}
              </div>
            ))}
        </section>
        <section className="panel">
          <div className="section-head">
            <strong>提示词模板</strong>
            <button type="button" className="secondary tiny-btn" onClick={() => void refreshPrompts()}>
              刷新
            </button>
          </div>
          <input value={promptTitle} onChange={(e) => setPromptTitle(e.target.value)} placeholder="模板标题" />
          <textarea
            value={promptContent}
            onChange={(e) => setPromptContent(e.target.value)}
            placeholder="在这里编写提示词模板..."
            rows={4}
          />
          <div className="row-actions">
            <button type="button" className="secondary tiny-btn" onClick={() => void checkPrompt()}>
              检查并补全
            </button>
            <button type="button" className="tiny-btn" onClick={() => void savePrompt()}>
              {editingPromptId ? "更新模板" : "保存模板"}
            </button>
          </div>
          {promptCheckInfo && <div className="hint">{promptCheckInfo}</div>}
          {promptsLoading && <div className="skeleton-list" />}
          {!promptsLoading && prompts.length === 0 && <div className="muted">暂无模板</div>}
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
                    使用
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
                    编辑
                  </button>
                  <button type="button" className="danger tiny-btn" onClick={() => void deletePrompt(p)}>
                    删除
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
          useWeb={useWeb}
          useReasoning={useReasoning}
          agentClassHint={agentClassHint}
          isAdmin={isAdmin}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          onThemeToggle={onThemeToggle}
          onUseWebChange={setUseWeb}
          onUseReasoningChange={setUseReasoning}
          onAgentClassHintChange={(v) => setAgentClassHint((v as AgentClassHint) || "")}
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
          onQuestionChange={setQuestion}
          onAsk={ask}
          onClearQuestion={() => setQuestion("")}
          onPromptPick={setQuestion}
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
