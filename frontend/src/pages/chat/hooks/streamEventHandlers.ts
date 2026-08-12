import type { Citation, SessionMessageMetadata } from "@/types/api";
import { mapRunStatus } from "@/pages/chat/constants";
import type { LegacyChatStreamEvent } from "./chatStreamAdapter";

export interface ExecutionStep {
  kind: string;
  label: string;
  detail?: string;
  at?: string;
}

type StoredGraphResult = NonNullable<SessionMessageMetadata["graph_result"]>;
type StoredGraphPath = StoredGraphResult["paths"][number];
type JsonRecord = Record<string, unknown>;

export interface StreamMetadata extends Omit<SessionMessageMetadata, "current_status" | "execution_steps" | "graph_result"> {
  current_status: string;
  execution_steps: ExecutionStep[];
  graph_result?: StoredGraphResult;
}

export interface StreamEventContext {
  answer: string;
  thoughts: string[];
  meta: StreamMetadata;
  executionSteps: ExecutionStep[];
  elapsedMs: () => number;
}

export interface StreamEventHandlers {
  handleStatusEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => { nextStatus: string; updatedCtx: StreamEventContext };
  handleRouteEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => StreamEventContext;
  handleThoughtEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => StreamEventContext;
  handleErrorEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => { error: Error; updatedCtx: StreamEventContext };
  handleVectorResultEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => StreamEventContext;
  handleGraphResultEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => StreamEventContext;
  handleWebResultEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => StreamEventContext;
  handleAnswerChunkEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => StreamEventContext;
  handleAnswerResetEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext) => StreamEventContext;
  handleDoneEvent: (evt: LegacyChatStreamEvent, ctx: StreamEventContext, retrievalStrategy: string) => StreamEventContext;
}

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : null;
}

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function readStringField(record: JsonRecord | null | undefined, key: string): string {
  return readString(record?.[key]);
}

function readBooleanField(record: JsonRecord | null | undefined, key: string): boolean {
  return record?.[key] === true;
}

function readArrayField(record: JsonRecord | null | undefined, key: string): unknown[] {
  return Array.isArray(record?.[key]) ? record[key] : [];
}

function displayValue(value: unknown): string {
  if (typeof value === "string") return value;
  const record = asRecord(value);
  if (!record) return "";
  return readString(record.name) || readString(record.entity) || readString(record.label) || readString(record.id);
}

function readStringArray(value: unknown): string[] {
  return (Array.isArray(value) ? value : [])
    .map(displayValue)
    .filter((item): item is string => item.length > 0);
}

function toCitation(value: unknown): Citation | null {
  const record = asRecord(value);
  if (!record) return null;
  return {
    source: readString(record.source),
    content: readString(record.content),
  };
}

function readCitations(value: unknown): Citation[] {
  return (Array.isArray(value) ? value : [])
    .map(toCitation)
    .filter((citation): citation is Citation => citation !== null);
}

function toGraphNeighbor(value: unknown): StoredGraphResult["neighbors"][number] | null {
  const record = asRecord(value);
  if (!record) return null;
  return {
    entity: displayValue(record.entity),
    relation: readString(record.relation),
    direction: readString(record.direction) === "out" ? "out" : "in",
  };
}

function toGraphPath(value: unknown): StoredGraphPath | null {
  const record = asRecord(value);
  if (!record) return null;

  const entities = readStringArray(record.entities);
  if (entities.length > 0) {
    return { entities, relations: readStringArray(record.relations) };
  }

  const source = readString(record.source);
  const middle = readString(record.middle);
  const target = readString(record.target);
  if (!source || !middle || !target) return null;
  return {
    source,
    rel1: readString(record.rel1) || undefined,
    middle,
    rel2: readString(record.rel2) || undefined,
    target,
  };
}

function toGraphResult(value: unknown): StoredGraphResult {
  const record = asRecord(value);
  return {
    neighbors: readArrayField(record, "neighbors")
      .map(toGraphNeighbor)
      .filter((neighbor): neighbor is StoredGraphResult["neighbors"][number] => neighbor !== null),
    paths: readArrayField(record, "paths")
      .map(toGraphPath)
      .filter((path): path is StoredGraphPath => path !== null),
    context: readStringField(record, "context"),
  };
}

function pushExecutionStep(ctx: StreamEventContext, kind: string, label: string, detail = ""): StreamEventContext {
  const step: ExecutionStep = { kind, label, detail, at: new Date().toISOString() };
  const updatedSteps = [...ctx.executionSteps, step].slice(-24);
  return {
    ...ctx,
    executionSteps: updatedSteps,
    meta: {
      ...ctx.meta,
      current_status: label,
      execution_steps: updatedSteps,
    },
  };
}

export function createStreamEventHandlers(): StreamEventHandlers {
  return {
    handleStatusEvent: (evt, ctx) => {
      const message = readStringField(evt, "message");
      const nextStatus = mapRunStatus(message);
      const updatedCtx = nextStatus ? pushExecutionStep(ctx, "status", nextStatus, message) : ctx;
      return {
        nextStatus,
        updatedCtx: {
          ...updatedCtx,
          meta: { ...updatedCtx.meta, current_status: nextStatus },
        },
      };
    },

    handleRouteEvent: (evt, ctx) => {
      const route = readStringField(evt, "route") || "unknown";
      const routeLabel = `路由完成: ${route}`;
      const detail = [
        readStringField(evt, "reason"),
        readStringField(evt, "skill") ? `skill=${readStringField(evt, "skill")}` : "",
        readStringField(evt, "agent_class") ? `agent=${readStringField(evt, "agent_class")}` : "",
      ].filter(Boolean).join(" | ");
      const updatedCtx = pushExecutionStep(ctx, "route", routeLabel, detail);
      return {
        ...updatedCtx,
        meta: {
          ...updatedCtx.meta,
          route,
          agent_class: readStringField(evt, "agent_class"),
          current_status: routeLabel,
        },
      };
    },

    handleThoughtEvent: (evt, ctx) => {
      const content = readStringField(evt, "content");
      if (!content) return ctx;
      const updatedThoughts = [...ctx.thoughts, content];
      const updatedCtx = pushExecutionStep(ctx, "thought", "分析判断", content);
      return { ...updatedCtx, thoughts: updatedThoughts };
    },

    handleErrorEvent: (evt, ctx) => {
      const reason = readStringField(evt, "message") || readStringField(evt, "error") || "stream error";
      const cost = ctx.elapsedMs();
      const updatedCtx = pushExecutionStep(ctx, "error", "执行失败", `${reason} | duration_ms=${cost}`);
      return {
        error: new Error(reason),
        updatedCtx: {
          ...updatedCtx,
          meta: { ...updatedCtx.meta, current_status: "执行失败", latency_ms: cost },
        },
      };
    },

    handleVectorResultEvent: (evt, ctx) => {
      const retrievedCount = Number(evt.retrieved_count || 0);
      const updatedCtx = pushExecutionStep(ctx, "vector", "向量检索完成", `命中片段 ${retrievedCount} 条`);
      return { ...updatedCtx, meta: { ...updatedCtx.meta, current_status: "向量检索完成" } };
    },

    handleGraphResultEvent: (evt, ctx) => {
      const entities = readStringArray(evt.entities);
      const graphResult = toGraphResult(evt);
      const updatedCtx = pushExecutionStep(
        ctx,
        "graph",
        "图谱检索完成",
        `命中 ${entities.length} 个实体, ${graphResult.neighbors.length} 个邻居关系, ${graphResult.paths.length} 条路径`,
      );
      return {
        ...updatedCtx,
        meta: {
          ...updatedCtx.meta,
          graph_entities: entities,
          graph_result: graphResult,
          current_status: "图谱检索完成",
        },
      };
    },

    handleWebResultEvent: (evt, ctx) => {
      const used = readBooleanField(evt, "used");
      const webLabel = used ? "联网补充完成" : "未触发联网补充";
      const updatedCtx = pushExecutionStep(ctx, "web", webLabel, `web_used=${used}`);
      return { ...updatedCtx, meta: { ...updatedCtx.meta, web_used: used, current_status: webLabel } };
    },

    handleAnswerChunkEvent: (evt, ctx) => ({
      ...ctx,
      answer: ctx.answer + readStringField(evt, "content"),
    }),

    handleAnswerResetEvent: (evt, ctx) => {
      const updatedCtx = pushExecutionStep(ctx, "rewrite", "答案已校正", "系统对流式答案做了一次重写或修正");
      return {
        ...updatedCtx,
        answer: readStringField(evt, "content"),
        meta: { ...updatedCtx.meta, current_status: "答案已校正" },
      };
    },

    handleDoneEvent: (evt, ctx, retrievalStrategy) => {
      const result = asRecord(evt.result) ?? {};
      const debug = asRecord(result.debug);
      const vectorResult = asRecord(result.vector_result);
      const graphResult = asRecord(result.graph_result);
      const webResult = asRecord(result.web_result);
      const finalAnswer = readString(result.answer) || ctx.answer;
      const cost = ctx.elapsedMs();
      const detail = [
        readString(result.route) ? `route=${readString(result.route)}` : "",
        readString(result.agent_class) ? `agent=${readString(result.agent_class)}` : "",
        webResult ? `web=${readBooleanField(webResult, "used")}` : "",
        `duration_ms=${cost}`,
      ].filter(Boolean).join(" | ");
      const updatedCtx = pushExecutionStep(ctx, "done", "执行完成", detail);
      const resultThoughts = readStringArray(result.thoughts);
      const resultGraphEntities = readStringArray(graphResult?.entities);
      return {
        ...updatedCtx,
        answer: finalAnswer,
        meta: {
          ...updatedCtx.meta,
          route: readString(result.route) || ctx.meta.route,
          execution_route: readString(result.execution_route) || readString(debug?.execution_route) || ctx.meta.execution_route,
          retrieval_strategy: readString(result.retrieval_strategy) || readString(debug?.retrieval_strategy) || retrievalStrategy,
          agent_class: readString(result.agent_class) || ctx.meta.agent_class,
          web_used: webResult ? readBooleanField(webResult, "used") : ctx.meta.web_used,
          latency_ms: cost,
          thoughts: resultThoughts.length > 0 ? resultThoughts : ctx.thoughts,
          graph_entities: resultGraphEntities.length > 0 ? resultGraphEntities : ctx.meta.graph_entities || [],
          current_status: "执行完成",
          citations: [...readCitations(vectorResult?.citations), ...readCitations(webResult?.citations)],
        },
      };
    },
  };
}
