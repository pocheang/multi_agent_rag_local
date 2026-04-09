import type { ChatMetadata } from "@/pages/chat/types";

export const QUICK_PROMPTS = [
  "分析这次告警可能的攻击链，并给出 P0/P1/P2 处置优先级",
  "针对暴露在公网的 Web 服务，给一份分层防护加固清单",
  "给出勒索事件的应急响应流程，包含证据保全和恢复步骤",
  "解释 SQL 注入的原理、常见检测信号和修复方案",
];

export const SUPPORTED_DOC_RE = /\.(md|txt|pdf|png|jpe?g|bmp|tiff?|webp)$/i;
export const SUPPORTED_CHAT_RE = /\.(pdf|png|jpe?g|bmp|tiff?|webp)$/i;

export const EMPTY_METADATA: ChatMetadata = {
  route: "",
  agent_class: "",
  web_used: false,
  thoughts: [],
  graph_entities: [],
  citations: [],
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
  };
  return map[statusKey] || statusKey || "";
}
