import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "@/styles/pages/landing-entry.css";
import { LanguageToggle } from "@/components/LanguageToggle";
import { DataFlowVisualization } from "@/components/DataFlowVisualization";

interface LandingPageProps {
  isLoggedIn: boolean;
}

export function LandingPage({ isLoggedIn }: LandingPageProps) {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    document.title = `${t("app.title")} - ${t("app.subtitle")}`;
  }, [i18n.language, t]);

  return (
    <div className="landing-root">
      {/* Background Orbs */}
      <div className="landing-orb-container" aria-hidden="true">
        <div className="landing-orb landing-orb-1" />
        <div className="landing-orb landing-orb-2" />
        <div className="landing-orb landing-orb-3" />
      </div>

      {/* Navigation Header */}
      <header className="landing-nav">
        <Link to="/" className="landing-logo">
          <svg width="24" height="24" viewBox="0 0 24 24" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-.778.099-1.533.284-2.253" />
          </svg>
          {t("app.title")}
        </Link>

        <nav className="landing-nav-links" aria-label="Main Navigation">
          <a href="#features" className="landing-nav-link">{i18n.language === "zh" ? "功能特性" : "Features"}</a>
          <a href="#workflow" className="landing-nav-link">{i18n.language === "zh" ? "运行流程" : "Execution Flow"}</a>
          <a href="#tiers" className="landing-nav-link">{i18n.language === "zh" ? "检索分级" : "Retrieval Tiers"}</a>
          <a href="#architecture" className="landing-nav-link">{i18n.language === "zh" ? "系统架构" : "Architecture"}</a>
        </nav>

        <div className="landing-nav-actions">
          <LanguageToggle />
          {isLoggedIn ? (
            <Link to="/app" className="landing-nav-btn primary">
              {t("pages.landing.enterApp")}
            </Link>
          ) : (
            <>
              <Link to="/app/login?mode=login" className="landing-nav-btn secondary">
                {t("auth.login")}
              </Link>
              <Link to="/app/login?mode=register" className="landing-nav-btn primary">
                {t("pages.landing.register")}
              </Link>
            </>
          )}
        </div>
      </header>

      {/* Hero Section */}
      <section className="landing-container">
        <div className="landing-hero">
          <h1>
            {i18n.language === "zh" ? (
              <>
                智询 QueryMind <br />
                <span>企业级智能问答引擎</span>
              </>
            ) : (
              <>
                QueryMind <br />
                <span>Enterprise Intelligent Q&A Engine</span>
              </>
            )}
          </h1>
          <p>{t("pages.landing.heroSubtitle")}</p>
          <div className="landing-hero-actions">
            {isLoggedIn ? (
              <Link to="/app" className="landing-hero-btn primary">
                {t("pages.landing.enterApp")}
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
              </Link>
            ) : (
              <>
                <Link to="/app/login?mode=login" className="landing-hero-btn primary">
                  {t("auth.login")}
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                </Link>
                <Link to="/app/login?mode=register" className="landing-hero-btn secondary">
                  {t("pages.landing.register")}
                </Link>
              </>
            )}
            <a href="#features" className="landing-hero-btn secondary">
              {t("pages.landing.learnMore")}
            </a>
          </div>
        </div>
      </section>

      {/* Features Grid Section */}
      <section id="features" className="landing-section">
        <div className="landing-container">
          <div className="landing-section-header">
            <h2>
              {i18n.language === "zh" ? (
                <>
                  六大生产级 <span>核心能力</span>
                </>
              ) : (
                <>
                  Six Production-Grade <span>Core Pillars</span>
                </>
              )}
            </h2>
            <p>{t("pages.landing.featuresSubtitle")}</p>
          </div>

          <div className="landing-features-grid">
            <div className="landing-feature-card">
              <div className="landing-feature-icon purple" aria-hidden="true">🧠</div>
              <h3>{t("pages.landing.feature1Title")}</h3>
              <p>{t("pages.landing.feature1Desc")}</p>
            </div>

            <div className="landing-feature-card">
              <div className="landing-feature-icon blue" aria-hidden="true">🔍</div>
              <h3>{t("pages.landing.feature2Title")}</h3>
              <p>{t("pages.landing.feature2Desc")}</p>
            </div>

            <div className="landing-feature-card">
              <div className="landing-feature-icon green" aria-hidden="true">🕸️</div>
              <h3>{t("pages.landing.feature3Title")}</h3>
              <p>{t("pages.landing.feature3Desc")}</p>
            </div>

            <div className="landing-feature-card">
              <div className="landing-feature-icon amber" aria-hidden="true">📄</div>
              <h3>{t("pages.landing.feature4Title")}</h3>
              <p>{t("pages.landing.feature4Desc")}</p>
            </div>

            <div className="landing-feature-card">
              <div className="landing-feature-icon red" aria-hidden="true">🔧</div>
              <h3>{t("pages.landing.feature5Title")}</h3>
              <p>{t("pages.landing.feature5Desc")}</p>
            </div>

            <div className="landing-feature-card">
              <div className="landing-feature-icon cyan" aria-hidden="true">🛡️</div>
              <h3>{t("pages.landing.feature6Title")}</h3>
              <p>{t("pages.landing.feature6Desc")}</p>
            </div>
          </div>
        </div>
      </section>

      {/* Execution Tiers Comparison */}
      <section id="tiers" className="landing-section">
        <div className="landing-container">
          <div className="landing-section-header">
            <h2>
              {i18n.language === "zh" ? (
                <>
                  分层执行 <span>检索系统</span>
                </>
              ) : (
                <>
                  Tiered Execution <span>Retrieval System</span>
                </>
              )}
            </h2>
            <p>
              {i18n.language === "zh"
                ? "根据查询复杂度与并发负载，自适应调度不同的执行策略，保障系统在高并发下的稳定性。"
                : "Dynamically adapt execution strategies based on query complexity and system load to ensure stable performance."}
            </p>
          </div>

          <div className="landing-tiers-grid">
            {/* Fast Tier */}
            <div className="landing-tier-card">
              <div className="landing-tier-header">
                <div className="landing-tier-name">{t("query.mode.fast")} (Fast)</div>
                <div className="landing-tier-desc">
                  {i18n.language === "zh" ? "适合简单事实性检索" : "Best for simple factual lookups"}
                </div>
              </div>
              <div className="landing-tier-metrics">
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "响应时间" : "Response Time"}</span>
                  <span className="landing-tier-metric-val">&lt; 800ms</span>
                </div>
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "检索深度" : "Retrieval Depth"}</span>
                  <span className="landing-tier-metric-val">top_k=5 / rr=3</span>
                </div>
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "限制 Tokens" : "Max Tokens"}</span>
                  <span className="landing-tier-metric-val">300</span>
                </div>
              </div>
              <ul className="landing-tier-features">
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "本地向量数据库检索" : "Local Vector DB retrieval"}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "BM25 关键词匹配" : "BM25 keyword matching"}
                </li>
                <li className="disabled">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "互联网搜索回退" : "Internet search fallback"}
                </li>
                <li className="disabled">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "多跳知识图谱推理" : "Multi-hop Graph reasoning"}
                </li>
              </ul>
            </div>

            {/* Balanced Tier */}
            <div className="landing-tier-card featured">
              <div className="landing-tier-header">
                <div className="landing-tier-name">{t("query.mode.balanced")} (Balanced)</div>
                <div className="landing-tier-desc">
                  {i18n.language === "zh" ? "常规业务知识问答" : "Standard Q&A workflows"}
                </div>
              </div>
              <div className="landing-tier-metrics">
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "响应时间" : "Response Time"}</span>
                  <span className="landing-tier-metric-val">&lt; 2000ms</span>
                </div>
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "检索深度" : "Retrieval Depth"}</span>
                  <span className="landing-tier-metric-val">top_k=10 / rr=5</span>
                </div>
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "限制 Tokens" : "Max Tokens"}</span>
                  <span className="landing-tier-metric-val">800</span>
                </div>
              </div>
              <ul className="landing-tier-features">
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "向量与 BM25 混合检索" : "Vector & BM25 hybrid search"}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "RRF 倒数排名融合" : "RRF candidate blending"}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "条件网络搜索回退" : "Conditional web search"}
                </li>
                <li className="disabled">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "深层图谱邻居推理" : "Deep Graph reasoning"}
                </li>
              </ul>
            </div>

            {/* Deep Tier */}
            <div className="landing-tier-card">
              <div className="landing-tier-header">
                <div className="landing-tier-name">{t("query.mode.deep")} (Deep)</div>
                <div className="landing-tier-desc">
                  {i18n.language === "zh" ? "复杂推演、多跳关联分析" : "Multi-step relational reasoning"}
                </div>
              </div>
              <div className="landing-tier-metrics">
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "响应时间" : "Response Time"}</span>
                  <span className="landing-tier-metric-val">&lt; 5000ms</span>
                </div>
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "检索深度" : "Retrieval Depth"}</span>
                  <span className="landing-tier-metric-val">top_k=20 / rr=10</span>
                </div>
                <div className="landing-tier-metric">
                  <span className="landing-tier-metric-label">{i18n.language === "zh" ? "限制 Tokens" : "Max Tokens"}</span>
                  <span className="landing-tier-metric-val">1500</span>
                </div>
              </div>
              <ul className="landing-tier-features">
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "最大深度向量与图谱检索" : "Max-depth Vector & Graph retrieval"}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "BGE 交叉编码重排" : "BGE reranker precision ranking"}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "主动联网搜索增强" : "Active web research fallback"}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {i18n.language === "zh" ? "Neo4j 实体关系路径提取" : "Neo4j relationship mapping"}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive Workflow Flow */}
      <section id="workflow" className="landing-section">
        <div className="landing-container">
          <div className="landing-section-header">
            <h2>{t("pages.landing.workflowTitle")}</h2>
            <p>{t("pages.landing.workflowSubtitle")}</p>
          </div>

          <div className="landing-workflow-flow">
            <div className="landing-workflow-step">
              <div className="landing-workflow-step-num">01</div>
              <div className="landing-workflow-step-body">
                <h4>{i18n.language === "zh" ? "安全接入与防护" : "Secure Gate & Guards"}</h4>
                <p>
                  {i18n.language === "zh"
                    ? "用户查询提交后，通过 RBAC 身份校验与安全网关，清洗 SQL 注入、有害指令，执行速率限制防护。"
                    : "Requests go through authentication, role checks, rate limiting, SQL injection protection, and input sanitization."}
                </p>
              </div>
            </div>

            <div className="landing-workflow-step">
              <div className="landing-workflow-step-num">02</div>
              <div className="landing-workflow-step-body">
                <h4>{i18n.language === "zh" ? "智能路由决策" : "Router Agent Routing"}</h4>
                <p>
                  {i18n.language === "zh"
                    ? "Router 节点基于本地大模型理解问题意图，进行中文 NLP 预处理和查询去重，并决定最佳检索模式。"
                    : "The Router analyzes query intent, applies NLP preprocessing/deduplication, and selects optimal agents."}
                </p>
              </div>
            </div>

            <div className="landing-workflow-step">
              <div className="landing-workflow-step-num">03</div>
              <div className="landing-workflow-step-body">
                <h4>{i18n.language === "zh" ? "多智能体并行检索" : "Parallel Search Operations"}</h4>
                <p>
                  {i18n.language === "zh"
                    ? "向量 RAG 检索 ChromaDB、图谱 RAG 检索 Neo4j 实体、网络 RAG 并行抓取，获取多路证据上下文。"
                    : "Vector RAG (ChromaDB), Graph RAG (Neo4j), and Web Research search in parallel to retrieve multi-source evidence."}
                </p>
              </div>
            </div>

            <div className="landing-workflow-step">
              <div className="landing-workflow-step-num">04</div>
              <div className="landing-workflow-step-body">
                <h4>{i18n.language === "zh" ? "答案合成与流式吐出" : "Answer Synthesis & SSE Streaming"}</h4>
                <p>
                  {i18n.language === "zh"
                    ? "Synthesis 代理整合证据链与上下文，生成带有引用标注的最终答复，并通过 SSE 管道流式推送至前端。"
                    : "The Synthesis agent compiles evidence with grounding, adds citations, and streams answers using SSE to the browser."}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive System Architecture visualization */}
      <section id="architecture" className="landing-section">
        <div className="landing-container">
          <div className="landing-section-header">
            <h2>
              {i18n.language === "zh" ? (
                <>
                  全链路 <span>系统架构图</span>
                </>
              ) : (
                <>
                  Full-Link <span>System Architecture</span>
                </>
              )}
            </h2>
            <p>
              {i18n.language === "zh"
                ? "系统底层基于 ReactFlow 渲染，直观展现多智能体协作、存储持久化、安全边界及治理运维模块的连接路径。"
                : "A fully interactive architecture graph rendering data flows, storage blocks, security scopes, and pipelines."}
            </p>
          </div>

          <div className="landing-arch-sandbox">
            <div className="landing-arch-overlay">
              {i18n.language === "zh" ? "💡 交互式预览：支持拖动和缩放" : "💡 Interactive Preview: Supports drag & zoom"}
            </div>
            <DataFlowVisualization />
          </div>
        </div>
      </section>

      {/* CTA section */}
      <section className="landing-cta">
        <div className="landing-container">
          <div className="landing-cta-banner">
            <h2>{t("pages.landing.ctaTitle")}</h2>
            <p>{t("pages.landing.ctaSubtitle")}</p>
            {isLoggedIn ? (
              <Link to="/app" className="landing-hero-btn secondary">
                {t("pages.landing.enterApp")}
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
              </Link>
            ) : (
              <div className="landing-cta-actions">
                <Link to="/app/login?mode=login" className="landing-hero-btn secondary">
                  {t("auth.loginButton")}
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                </Link>
                <Link to="/app/login?mode=register" className="landing-hero-btn landing-hero-btn-light-outline">
                  {t("pages.landing.register")}
                </Link>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="landing-container">
          <div className="landing-footer-links">
            <a href="#features" className="landing-footer-link">{i18n.language === "zh" ? "功能" : "Features"}</a>
            <a href="#workflow" className="landing-footer-link">{i18n.language === "zh" ? "流转" : "Flow"}</a>
            <a href="#tiers" className="landing-footer-link">{i18n.language === "zh" ? "分级" : "Tiers"}</a>
            <Link to="/app/architecture" className="landing-footer-link">
              {t("dataFlow.title")}
            </Link>
          </div>
          <p>© {new Date().getFullYear()} {t("app.title")}. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
