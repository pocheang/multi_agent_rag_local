import type { ChatMetadata } from "@/pages/chat/types";

export const QUICK_PROMPTS = [
  "对这次告警做攻击链复盘，并按 P0/P1/P2 给出处置优先级",
  "切换到 pdf_text 模式：总结这份 PDF 的关键信息、风险和证据页码",
  "切换到 cybersecurity 模式：给互联网暴露服务输出分层加固清单",
  "用 general 模式做管理摘要：用 5 条要点汇报当前风险状态",
];

export const SUPPORTED_DOC_RE = /\.(md|txt|pdf|png|jpe?g|bmp|tiff?|webp)$/i;
export const SUPPORTED_CHAT_RE = /\.(pdf|png|jpe?g|bmp|tiff?|webp)$/i;

export const EMPTY_METADATA: ChatMetadata = {
  route: "",
  execution_route: "",
  retrieval_strategy: "",
  agent_class: "",
  web_used: false,
  latency_ms: 0,
  thoughts: [],
  graph_entities: [],
  citations: [],
  current_status: "",
  execution_steps: [],
};

export function isMobile() {
  return window.matchMedia("(max-width: 1080px)").matches;
}

export function mapRunStatus(statusKey: string) {
  const map: Record<string, string> = {
    routing: "路由中",
    retrieving_vector: "检索向量库",
    retrieving_graph: "检索图谱",
    retrieving_web: "联网补充",
    synthesizing: "生成回答",
    pdf_upload_required: "需要先上传文档",
    pdf_selection_required: "需要选择文档",
    pdf_reindex_required: "需要重建索引",
    cache_hit: "命中缓存",
    heartbeat: "保持连接",
    trace: "建立追踪",
  };
  return map[statusKey] || statusKey || "";
}
