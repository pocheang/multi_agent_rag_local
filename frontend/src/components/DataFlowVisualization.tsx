import { useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  type ReactFlowInstance,
} from 'reactflow';
import 'reactflow/dist/style.css';
import '@/styles/components/data-flow.css';

// Node translations
const nodeTranslations: Record<string, { zh: string; en: string }> = {
  '1': {
    zh: '🌐 Browser UI\n用户界面',
    en: '🌐 Browser UI\nUser Interface'
  },
  '2': {
    zh: '🔐 认证层 /auth/login\nJWT + HttpOnly Cookie\nPBKDF2 哈希 + Salt',
    en: '🔐 Auth Layer /auth/login\nJWT + HttpOnly Cookie\nPBKDF2 Hash + Salt'
  },
  '3': {
    zh: '📡 查询入口 /query/stream\nBearer Token + RBAC\n用户/管理员角色隔离',
    en: '📡 Query Entry /query/stream\nBearer Token + RBAC\nUser/Admin Role Isolation'
  },
  '4': {
    zh: '✅ 安全检查\n输入规范化\n危险指令拦截\nSQL注入防护',
    en: '✅ Security Check\nInput Normalization\nDangerous Command Block\nSQL Injection Protection'
  },
  '5': {
    zh: '⏱️ 速率限制\n管理员 1-5 req/hour\n查询配额控制',
    en: '⏱️ Rate Limit\nAdmin 1-5 req/hour\nQuery Quota Control'
  },
  '6': {
    zh: '🔤 中文NLP预处理\n分词 + 同义词扩展\n查询重写去重优化',
    en: '🔤 Chinese NLP\nTokenization + Synonyms\nQuery Rewrite & Dedup'
  },
  '7': {
    zh: '🧠 高级RAG处理\n查询分解\nSelf-RAG 评估',
    en: '🧠 Advanced RAG\nQuery Decomposition\nSelf-RAG Evaluation'
  },
  '8': {
    zh: '🎯 Router Agent\nLangGraph 工作流\n条件路由 + 分层执行\nFast/Balanced/Deep',
    en: '🎯 Router Agent\nLangGraph Workflow\nConditional Routing\nFast/Balanced/Deep'
  },
  '9': {
    zh: '🔍 Vector RAG Agent\n混合检索 Vector+BM25\nRRF 融合\nBGE-reranker-v2-m3',
    en: '🔍 Vector RAG Agent\nHybrid Retrieval Vector+BM25\nRRF Fusion\nBGE-reranker-v2-m3'
  },
  '10': {
    zh: '🕸️ Graph RAG Agent\nNeo4j 实体匹配\n邻居关系查询\nAPOC 插件',
    en: '🕸️ Graph RAG Agent\nNeo4j Entity Matching\nNeighbor Relations\nAPOC Plugin'
  },
  '11': {
    zh: '🌍 Web Research Agent\n外部搜索引擎\n实时信息获取',
    en: '🌍 Web Research Agent\nExternal Search Engine\nReal-time Info'
  },
  '12': {
    zh: '🤖 ReAct Agent\nReasoning + Acting\n迭代工具调用 (最多5轮)',
    en: '🤖 ReAct Agent\nReasoning + Acting\nIterative Tool Use (max 5 cycles)'
  },
  '13': {
    zh: '✨ Synthesis Agent\n答案生成 + 引用\n上下文整合',
    en: '✨ Synthesis Agent\nAnswer Generation + Citations\nContext Integration'
  },
  '30': {
    zh: '🎯 Route Validator Agent\n路由验证代理\n3层验证 (95%+准确率)\n规则+置信度+LLM',
    en: '🎯 Route Validator Agent\nRoute Validation Agent\n3-Layer Validation (95%+)\nRule+Confidence+LLM'
  },
  '31': {
    zh: '📊 Retrieval Quality Agent\n检索质量代理\n多维度指标评估\nPrecision+Recall+F1',
    en: '📊 Retrieval Quality Agent\nRetrieval Quality Agent\nMulti-dimensional Metrics\nPrecision+Recall+F1'
  },
  '32': {
    zh: '🛡️ Answer Validator Agent\n答案验证代理\nNLI幻觉检测 (92%+)\n3层验证流水线',
    en: '🛡️ Answer Validator Agent\nAnswer Validation Agent\nNLI Hallucination (92%+)\n3-Level Pipeline'
  },
  '33': {
    zh: '💭 Context Tracker Agent\n上下文跟踪代理\n多轮对话追踪 (50轮)\n线程安全LRU缓存',
    en: '💭 Context Tracker Agent\nContext Tracking Agent\nMulti-turn Tracking (50)\nThread-safe LRU Cache'
  },
  '34': {
    zh: '⚖️ Quality Orchestrator Agent\n质量编排代理\n分数融合 + 决策逻辑\n接受/优化/拒绝',
    en: '⚖️ Quality Orchestrator Agent\nQuality Orchestration Agent\nScore Fusion + Decision\nAccept/Refine/Reject'
  },
  '14': {
    zh: '💾 ChromaDB\n向量索引\n父子分块策略\nparent 1500 / child 600',
    en: '💾 ChromaDB\nVector Index\nParent-Child Chunks\nparent 1500 / child 600'
  },
  '15': {
    zh: '📊 BM25 + JSONL\nchunks.jsonl\nparents.jsonl\n稀疏检索',
    en: '📊 BM25 + JSONL\nchunks.jsonl\nparents.jsonl\nSparse Retrieval'
  },
  '16': {
    zh: '🗄️ Neo4j 5.26\n关系图谱\nAPOC 插件\n实体关系',
    en: '🗄️ Neo4j 5.26\nKnowledge Graph\nAPOC Plugin\nEntity Relations'
  },
  '17': {
    zh: '📄 文档处理\n流式PDF (70%内存优化)\nOCR (Tesseract)\n图像字幕',
    en: '📄 Document Processing\nStreaming PDF (70% Memory)\nOCR (Tesseract)\nImage Captions'
  },
  '18': {
    zh: '📤 SSE 流式返回\nchunk 返回\n心跳保活\nAgent 执行追踪',
    en: '📤 SSE Streaming\nChunk Response\nHeartbeat Keepalive\nAgent Execution Tracking'
  },
  '19': {
    zh: '💿 SQLite 持久化\n用户 + 会话\n审计日志\nPrompt版本 + API设置',
    en: '💿 SQLite Persistence\nUsers + Sessions\nAudit Log\nPrompt Version + API Config'
  },
  '20': {
    zh: '📁 会话历史\nsessions/user_*/*.json\n按用户隔离\n多会话管理',
    en: '📁 Session History\nsessions/user_*/*.json\nUser Isolation\nMulti-Session Management'
  },
  '21': {
    zh: '📂 文件存储\nuploads/user_*/\nOCR 缓存\n文档管理',
    en: '📂 File Storage\nuploads/user_*/\nOCR Cache\nDocument Management'
  },
  '22': {
    zh: '📊 运维监控\n金丝雀路由\n配置回滚\n基准测试 + 查询重放',
    en: '📊 Ops Monitoring\nCanary Routing\nConfig Rollback\nBenchmark + Query Replay'
  },
  '23': {
    zh: '🔧 Prompt 管理\n版本控制\n审批流 + 回滚\n性能对比',
    en: '🔧 Prompt Management\nVersion Control\nApproval + Rollback\nPerformance Comparison'
  },
  '24': {
    zh: '🛡️ 熔断器\n故障隔离\n舱壁模式\n重试逻辑',
    en: '🛡️ Circuit Breaker\nFault Isolation\nBulkhead Pattern\nRetry Logic'
  },
  '25': {
    zh: '⚡ 负载降级\n高负载检测 (>80%)\n自动降档\nFast/Balanced/Deep',
    en: '⚡ Load Degradation\nHigh Load Detection (>80%)\nAuto Downgrade\nFast/Balanced/Deep'
  },
  '26': {
    zh: '💨 内存缓存\n检索配置缓存\n运行时状态\n热数据加速',
    en: '💨 Memory Cache\nRetrieval Config Cache\nRuntime State\nHot Data Acceleration'
  },
  '27': {
    zh: '🔒 API密钥加密\nAES加密存储\n白名单URL验证\n安全配置管理',
    en: '🔒 API Key Encryption\nAES Encrypted Storage\nURL Whitelist\nSecure Config Management'
  },
  '28': {
    zh: '🚀 CI/CD 质门\n自动化RAG评估\n性能基准测试\n回归测试',
    en: '🚀 CI/CD Quality Gate\nAutomated RAG Evaluation\nPerformance Benchmarks\nRegression Testing'
  },
  '29': {
    zh: '📈 批量图表提取\n并行处理\n吞吐量优化\n图像分析',
    en: '📈 Batch Chart Extraction\nParallel Processing\nThroughput Optimization\nImage Analysis'
  }
};

const initialNodes: Node[] = [
  // ========== Layer 0: User Interface (y: 0-100) ==========
  { id: '1', type: 'default', data: { label: '' }, position: { x: 600, y: 0 }, className: 'node-browser' },

  // ========== Layer 1: Authentication & Security (y: 200-300) ==========
  { id: '2', type: 'default', data: { label: '' }, position: { x: 600, y: 200 }, className: 'node-auth' },
  { id: '27', type: 'default', data: { label: '' }, position: { x: 1000, y: 200 }, className: 'node-auth' },

  // ========== Layer 2: Query Entry & Validation (y: 400-500) ==========
  { id: '3', type: 'default', data: { label: '' }, position: { x: 600, y: 400 }, className: 'node-query' },
  { id: '4', type: 'default', data: { label: '' }, position: { x: 400, y: 500 }, className: 'node-validation' },
  { id: '5', type: 'default', data: { label: '' }, position: { x: 800, y: 500 }, className: 'node-validation' },

  // ========== Layer 3: NLP Preprocessing (y: 700-800) ==========
  { id: '6', type: 'default', data: { label: '' }, position: { x: 600, y: 700 }, className: 'node-nlp' },
  { id: '7', type: 'default', data: { label: '' }, position: { x: 600, y: 850 }, className: 'node-nlp' },
  { id: '24', type: 'default', data: { label: '' }, position: { x: 1000, y: 700 }, className: 'node-validation' },
  { id: '25', type: 'default', data: { label: '' }, position: { x: 1000, y: 850 }, className: 'node-validation' },

  // ========== Layer 4: Router & Route Validation (y: 1000-1050) ==========
  { id: '8', type: 'default', data: { label: '' }, position: { x: 600, y: 1000 }, className: 'node-router' },
  { id: '30', type: 'default', data: { label: '' }, position: { x: 200, y: 1000 }, className: 'node-validation' },
  { id: '23', type: 'default', data: { label: '' }, position: { x: 1000, y: 1000 }, className: 'node-validation' },

  // ========== Layer 5: AI Agents (y: 1200) ==========
  { id: '9', type: 'default', data: { label: '' }, position: { x: 100, y: 1200 }, className: 'node-agent' },
  { id: '10', type: 'default', data: { label: '' }, position: { x: 300, y: 1200 }, className: 'node-agent' },
  { id: '11', type: 'default', data: { label: '' }, position: { x: 500, y: 1200 }, className: 'node-agent' },
  { id: '12', type: 'default', data: { label: '' }, position: { x: 700, y: 1200 }, className: 'node-agent' },
  { id: '13', type: 'default', data: { label: '' }, position: { x: 900, y: 1200 }, className: 'node-agent' },
  { id: '26', type: 'default', data: { label: '' }, position: { x: 1100, y: 1200 }, className: 'node-retrieval' },

  // ========== Layer 6: Data Retrieval (y: 1400) ==========
  { id: '14', type: 'default', data: { label: '' }, position: { x: 100, y: 1400 }, className: 'node-retrieval' },
  { id: '15', type: 'default', data: { label: '' }, position: { x: 300, y: 1400 }, className: 'node-retrieval' },
  { id: '16', type: 'default', data: { label: '' }, position: { x: 500, y: 1400 }, className: 'node-retrieval' },
  { id: '17', type: 'default', data: { label: '' }, position: { x: 700, y: 1400 }, className: 'node-retrieval' },
  { id: '29', type: 'default', data: { label: '' }, position: { x: 900, y: 1400 }, className: 'node-retrieval' },

  // ========== Layer 7: Retrieval Quality Check (y: 1550) ==========
  { id: '31', type: 'default', data: { label: '' }, position: { x: 400, y: 1550 }, className: 'node-validation' },

  // ========== Layer 8: Synthesis & Answer Generation (y: 1700) ==========
  { id: '18', type: 'default', data: { label: '' }, position: { x: 600, y: 1700 }, className: 'node-output' },
  { id: '22', type: 'default', data: { label: '' }, position: { x: 1000, y: 1700 }, className: 'node-validation' },

  // ========== Layer 9: Quality Assurance (y: 1900-2000) ==========
  { id: '32', type: 'default', data: { label: '' }, position: { x: 400, y: 1900 }, className: 'node-validation' },
  { id: '33', type: 'default', data: { label: '' }, position: { x: 800, y: 1900 }, className: 'node-validation' },
  { id: '34', type: 'default', data: { label: '' }, position: { x: 600, y: 2050 }, className: 'node-validation' },
  { id: '28', type: 'default', data: { label: '' }, position: { x: 1000, y: 2000 }, className: 'node-validation' },

  // ========== Layer 10: Final Output (y: 2250) ==========
  { id: '19', type: 'default', data: { label: '' }, position: { x: 400, y: 2250 }, className: 'node-output' },
  { id: '20', type: 'default', data: { label: '' }, position: { x: 600, y: 2250 }, className: 'node-output' },
  { id: '21', type: 'default', data: { label: '' }, position: { x: 800, y: 2250 }, className: 'node-output' },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e2-3', source: '2', target: '3', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e3-4', source: '3', target: '4', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e3-5', source: '3', target: '5', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e4-6', source: '4', target: '6', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e5-6', source: '5', target: '6', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e6-7', source: '6', target: '7', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e7-8', source: '7', target: '8', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  // Quality Assurance Flow - New in v0.5.0
  { id: 'e8-30', source: '8', target: '30', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e30-9', source: '30', target: '9', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e30-10', source: '30', target: '10', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e30-11', source: '30', target: '11', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e30-12', source: '30', target: '12', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e30-13', source: '30', target: '13', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e14-31', source: '14', target: '31', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e15-31', source: '15', target: '31', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e16-31', source: '16', target: '31', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e17-31', source: '17', target: '31', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e18-32', source: '18', target: '32', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e18-33', source: '18', target: '33', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e32-34', source: '32', target: '34', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e33-34', source: '33', target: '34', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e31-34', source: '31', target: '34', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e30-34', source: '30', target: '34', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  { id: 'e34-19', source: '34', target: '19', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#10b981' } },
  // Original Flow
  { id: 'e8-9', source: '8', target: '9', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e8-10', source: '8', target: '10', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e8-11', source: '8', target: '11', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e8-12', source: '8', target: '12', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e8-13', source: '8', target: '13', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e9-14', source: '9', target: '14', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e9-15', source: '9', target: '15', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e10-16', source: '10', target: '16', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e11-17', source: '11', target: '17', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e12-14', source: '12', target: '14', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#9333ea' } },
  { id: 'e12-15', source: '12', target: '15', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#9333ea' } },
  { id: 'e12-16', source: '12', target: '16', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#9333ea' } },
  { id: 'e12-17', source: '12', target: '17', animated: true, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#9333ea' } },
  { id: 'e14-18', source: '14', target: '18', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e15-18', source: '15', target: '18', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e16-18', source: '16', target: '18', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e17-18', source: '17', target: '18', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e13-18', source: '13', target: '18', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e18-19', source: '18', target: '19', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e18-20', source: '18', target: '20', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e18-21', source: '18', target: '21', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e8-23', source: '8', target: '23', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#ed8936' } },
  { id: 'e18-22', source: '18', target: '22', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#ed8936' } },
  { id: 'e6-24', source: '6', target: '24', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#4a5568', strokeDasharray: '5,5' } },
  { id: 'e8-25', source: '8', target: '25', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#4a5568', strokeDasharray: '5,5' } },
  { id: 'e14-26', source: '14', target: '26', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#48bb78', strokeDasharray: '5,5' } },
  { id: 'e15-26', source: '15', target: '26', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#48bb78', strokeDasharray: '5,5' } },
  { id: 'e16-26', source: '16', target: '26', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#48bb78', strokeDasharray: '5,5' } },
  { id: 'e3-27', source: '3', target: '27', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#5a67d8', strokeDasharray: '5,5' } },
  { id: 'e18-28', source: '18', target: '28', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#ed8936', strokeDasharray: '5,5' } },
  { id: 'e17-29', source: '17', target: '29', animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#48bb78', strokeDasharray: '5,5' } },
];

export function DataFlowVisualization() {
  const { i18n } = useTranslation();
  const flowRef = useRef<ReactFlowInstance | null>(null);

  const translatedNodes = useMemo(() => {
    const lang = i18n.language === 'zh' ? 'zh' : 'en';
    return initialNodes.map(node => ({
      ...node,
      data: { label: nodeTranslations[node.id][lang] }
    }));
  }, [i18n.language]);

  const [nodes, setNodes, onNodesChange] = useNodesState(translatedNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const fitGraph = useMemo(
    () => () => {
      if (typeof window === 'undefined') {
        return;
      }

      const padding = window.innerWidth <= 768 ? 0.2 : 0.14;
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          flowRef.current?.fitView({ padding, duration: 300 });
        });
      });
    },
    []
  );

  useEffect(() => {
    const lang = i18n.language === 'zh' ? 'zh' : 'en';
    const updatedNodes = initialNodes.map(node => ({
      ...node,
      data: { label: nodeTranslations[node.id][lang] }
    }));
    setNodes(updatedNodes);
    fitGraph();
  }, [fitGraph, i18n.language, setNodes]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const handleResize = () => {
      fitGraph();
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [fitGraph]);

  return (
    <div className="reactflow-wrapper">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.14 }}
        minZoom={0.15}
        maxZoom={1.5}
        onInit={(instance) => {
          flowRef.current = instance;
          fitGraph();
        }}
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
