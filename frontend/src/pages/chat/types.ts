import type React from "react";
import type { AuthUser, Citation, SessionMessage } from "@/types/api";

export type Props = {
  user: AuthUser | null;
  onLogout: () => Promise<void>;
  themeLabel: string;
  onThemeToggle: () => void;
};

export type Toast = {
  id: string;
  text: string;
  kind: "info" | "success" | "warn" | "error";
};

export type GraphEntity = {
  name: string;
  type: string;
  description?: string;
};

export type GraphNeighbor = {
  entity: string;
  relation: string;
  direction: "in" | "out";
};

export type GraphPath = {
  entities: string[];
  relations: string[];
};

export type GraphResult = {
  entities: GraphEntity[];
  neighbors: GraphNeighbor[];
  paths: GraphPath[];
  context?: string;
};

export type ChatMetadata = {
  route: string;
  execution_route?: string;
  retrieval_strategy?: string;
  agent_class: string;
  web_used: boolean;
  latency_ms?: number;
  thoughts: string[];
  graph_entities: string[];
  graph_result?: GraphResult;
  citations: Citation[];
  current_status?: string;
  execution_steps?: Array<{
    kind: string;
    label: string;
    detail?: string;
    at?: string;
  }>;
};

export type SetString = React.Dispatch<React.SetStateAction<string>>;
export type SetBoolean = React.Dispatch<React.SetStateAction<boolean>>;
export type SetMessageList = React.Dispatch<React.SetStateAction<SessionMessage[]>>;
