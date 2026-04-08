import { Link } from "react-router-dom";

type Props = {
  isLoggedIn: boolean;
  themeLabel: string;
  onThemeToggle: () => void;
};

export function ArchitecturePage({ isLoggedIn, themeLabel, onThemeToggle }: Props) {
  return (
    <div className="admin-shell architecture-shell">
      <header className="topbar">
        <div>
          <h2>CyberSec RAG Architecture</h2>
          <p className="muted">前端、鉴权、检索编排、存储和流式响应的全链路总览。</p>
        </div>
        <div className="top-actions">
          <button type="button" className="secondary" onClick={onThemeToggle}>
            {themeLabel}
          </button>
          <Link className="secondary link-btn" to={isLoggedIn ? "/app" : "/app/login"}>
            {isLoggedIn ? "返回系统" : "去登录"}
          </Link>
        </div>
      </header>

      <section className="panel">
        <div className="section-head">
          <strong>1. 全链路数据流</strong>
        </div>
        <pre className="diagram-block">{`Browser UI
  -> /auth/login
  -> /query/stream (Bearer token)
      -> 输入规范化 + 安全检查
      -> Router Agent (vector / graph / hybrid / web)
      -> 检索层 (Chroma + BM25 + RRF + Reranker + Neo4j)
      -> Synthesis Agent
      -> SSE 流式返回
      -> 会话历史落盘 (per-user sessions/*.json)`}</pre>
      </section>

      <section className="architecture-grid">
        <article className="panel">
          <div className="section-head">
            <strong>2. 核心方法</strong>
          </div>
          <ul className="compact-list">
            <li>混合检索：Vector + Sparse + RRF + Rerank</li>
            <li>图谱检索：实体匹配 + 邻居关系</li>
            <li>多智能体路由：按问题类型分配路径</li>
            <li>流式生成：SSE 按 chunk 返回</li>
            <li>Prompt 质检：检查并补全模板结构</li>
          </ul>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>3. 数据库与存储</strong>
          </div>
          <ul className="compact-list">
            <li>SQLite：用户、登录会话、审计日志、Prompt</li>
            <li>Chroma：向量索引</li>
            <li>Neo4j：关系图谱</li>
            <li>JSONL：BM25 语料</li>
            <li>JSON：多会话历史（按用户隔离）</li>
          </ul>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>4. 安全能力</strong>
          </div>
          <ul className="compact-list">
            <li>PBKDF2 密码哈希 + salt</li>
            <li>Bearer 鉴权 + 过期机制</li>
            <li>输入安全检查与危险指令拦截</li>
            <li>按用户隔离上传目录与会话文件</li>
          </ul>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>5. 关键接口</strong>
          </div>
          <pre className="diagram-block">{`POST /auth/register
POST /auth/login
GET  /auth/me
POST /query
POST /query/stream
GET  /sessions
PATCH /sessions/{id}/messages/{message_id}
GET  /documents
POST /upload
GET  /prompts
POST /prompts/check`}</pre>
        </article>
      </section>
    </div>
  );
}
