"""
Frontend-Controlled Hybrid Mode Design (v2 - Fixed)
前端控制的混合模式设计（修复版）

修复了v1的5个关键问题：
1. 安全漏洞 - 后端强制限制成本控制参数
2. 会话一致性 - session-level偏好而非request-level
3. 成本追踪 - 细粒度成本计算
4. 架构清晰 - 服务职责明确
5. 降级策略 - 预算耗尽时的优雅降级
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class HybridMode(str, Enum):
    """混合模式枚举"""
    RULE_ONLY = "rule_only"           # 纯规则（免费）
    CONSERVATIVE = "conservative"     # 保守混合（推荐）
    BALANCED = "balanced"             # 平衡混合
    AGGRESSIVE = "aggressive"         # 激进混合


class BudgetExceededAction(str, Enum):
    """预算耗尽时的行为"""
    DOWNGRADE = "downgrade"           # 自动降级到规则模式
    REJECT = "reject"                 # 拒绝请求，返回错误
    CONTINUE_UNTRACKED = "continue"   # 继续但不计费（体验模式）


# ============================================================================
# Session-Level Preferences (存储在session中)
# ============================================================================

class SessionClarificationPreferences(BaseModel):
    """会话级别的澄清偏好（在session创建时设置，整个session保持一致）"""

    # 混合模式
    mode: HybridMode = Field(
        default=HybridMode.RULE_ONLY,
        description="混合模式：rule_only/conservative/balanced/aggressive"
    )

    # 预算控制（后端强制限制）
    session_budget_usd: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,  # 单session最多$1，后端强制
        description="本session预算上限（美元），超出后执行budget_exceeded_action"
    )

    budget_exceeded_action: BudgetExceededAction = Field(
        default=BudgetExceededAction.DOWNGRADE,
        description="预算耗尽时的行为"
    )

    # 用户ID（用于跨session的月度预算控制）
    user_id: Optional[str] = Field(
        default=None,
        description="用户ID，用于月度预算追踪"
    )

    @field_validator('session_budget_usd')
    @classmethod
    def validate_budget(cls, v):
        """后端强制：单session预算不能超过$1"""
        if v is not None and v > 1.0:
            raise ValueError("单session预算不能超过$1.00")
        return v


# ============================================================================
# Request-Level Context (每次请求传递澄清上下文)
# ============================================================================

class ClarificationContext(BaseModel):
    """澄清上下文（多轮澄清时传递）"""

    round_number: int = Field(default=1, ge=1, description="当前澄清轮次")

    collected_info: dict[str, str] = Field(
        default_factory=dict,
        description="已收集的信息 {field_name: value}"
    )

    intent: Optional[str] = Field(None, description="已识别的意图")

    # 成本追踪（累计）
    total_llm_calls: int = Field(default=0, description="累计LLM调用次数")
    total_cost_usd: float = Field(default=0.0, description="累计成本（美元）")


class EnhancedQueryRequest(BaseModel):
    """增强的查询请求"""

    question: str = Field(..., description="用户问题")

    session_id: str = Field(..., description="会话ID")

    # Session偏好（首次创建session时设置，之后从session中读取）
    session_preferences: Optional[SessionClarificationPreferences] = Field(
        default=None,
        description="Session偏好（仅在创建session时传递，后续请求从后端读取）"
    )

    # 澄清上下文（多轮澄清）
    clarification_context: Optional[ClarificationContext] = Field(
        default=None,
        description="澄清上下文（多轮澄清时传递）"
    )


# ============================================================================
# Response with Fine-Grained Cost Tracking
# ============================================================================

class LLMCallDetail(BaseModel):
    """单次LLM调用详情"""

    operation: str = Field(..., description="操作类型：intent/extract/generate")
    model: str = Field(..., description="使用的模型")
    input_tokens: int = Field(..., description="输入token数")
    output_tokens: int = Field(..., description="输出token数")
    cost_usd: float = Field(..., description="本次调用成本（美元）")
    latency_ms: int = Field(..., description="延迟（毫秒）")


class ClarificationResponse(BaseModel):
    """澄清响应"""

    action: Literal["CONTINUE", "NEED_CLARIFICATION"] = Field(
        ...,
        description="下一步动作"
    )

    # 如果需要澄清
    question: Optional[str] = Field(None, description="澄清问题")
    options: Optional[list[str]] = Field(None, description="选项列表")
    field_name: Optional[str] = Field(None, description="字段名")

    # 元数据
    intent: str = Field(..., description="识别的意图")
    confidence: float = Field(..., description="置信度")

    # 细粒度成本追踪
    llm_calls: list[LLMCallDetail] = Field(
        default_factory=list,
        description="本次请求的LLM调用详情"
    )

    total_cost_this_request: float = Field(
        default=0.0,
        description="本次请求总成本（美元）"
    )

    # Session累计成本
    session_total_cost: float = Field(
        default=0.0,
        description="本session累计成本（美元）"
    )

    session_budget_remaining: Optional[float] = Field(
        None,
        description="本session剩余预算（美元），None表示无预算限制"
    )

    # 降级信息
    downgraded: bool = Field(
        default=False,
        description="是否因预算不足而降级到规则模式"
    )

    downgrade_reason: Optional[str] = Field(
        None,
        description="降级原因"
    )


# ============================================================================
# Backend Service Architecture (清晰的服务职责)
# ============================================================================

"""
正确的架构设计：

┌─────────────────────────────────────────────────────────────┐
│  API Layer (app/api/routes/public/chat.py)                  │
│  - 解析请求                                                  │
│  - 读取session偏好（首次从请求，后续从DB）                  │
│  - 调用 EnhancedRouterService                               │
│  - 追踪成本，更新session状态                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  EnhancedRouterService (app/agents/router/enhanced_service.py)│
│  - 接收 session_preferences                                 │
│  - 根据 mode 决定是否使用 HybridClarificationService       │
│  - 统一的澄清流程入口                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴────────────────────┐
        ↓                                        ↓
┌──────────────────────┐          ┌──────────────────────────┐
│  Rule-Based Logic    │          │  HybridClarificationSvc  │
│  (内置规则)          │          │  (规则 + LLM fallback)   │
└──────────────────────┘          └──────────────────────────┘

关键点：
1. API层只负责请求解析、session管理、成本追踪
2. EnhancedRouterService根据session偏好决定使用哪种策略
3. 不在API层做if/else选择服务，保持单一入口
"""


# ============================================================================
# Cost Calculation (细粒度成本计算)
# ============================================================================

class CostCalculator:
    """LLM调用成本计算器"""

    # 模型定价（每1K tokens，美元）
    PRICING = {
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    }

    @classmethod
    def calculate(
        cls,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """计算单次调用成本"""
        pricing = cls.PRICING.get(model, cls.PRICING["gpt-4o-mini"])
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost

    @classmethod
    def estimate_for_operation(cls, operation: str, model: str = "gpt-4o-mini") -> float:
        """估算操作成本（用于预算判断）"""
        estimates = {
            "intent": (200, 50),      # 意图识别：简单prompt
            "extract": (800, 200),    # 信息提取：较长上下文
            "generate": (500, 150),   # 问题生成：中等复杂度
        }
        input_tokens, output_tokens = estimates.get(operation, (500, 100))
        return cls.calculate(model, input_tokens, output_tokens)


# ============================================================================
# Budget Control (预算控制)
# ============================================================================

class BudgetController:
    """预算控制器"""

    # 后端强制限制
    MAX_SESSION_BUDGET = 1.0      # 单session最多$1
    MAX_MONTHLY_BUDGET = 50.0     # 单用户每月最多$50

    def __init__(self, session_prefs: SessionClarificationPreferences):
        self.session_prefs = session_prefs
        self.session_spent = 0.0

    def can_afford(self, operation: str, model: str = "gpt-4o-mini") -> tuple[bool, Optional[str]]:
        """检查是否有预算执行操作"""

        # 无预算限制
        if self.session_prefs.session_budget_usd is None:
            return True, None

        # 估算操作成本
        estimated_cost = CostCalculator.estimate_for_operation(operation, model)

        # 检查session预算
        remaining = self.session_prefs.session_budget_usd - self.session_spent
        if remaining < estimated_cost:
            return False, f"session预算不足（剩余${remaining:.4f}，需要${estimated_cost:.4f}）"

        return True, None

    def record_spending(self, cost: float):
        """记录花费"""
        self.session_spent += cost

    def should_downgrade(self) -> bool:
        """是否应该降级到规则模式"""
        if self.session_prefs.session_budget_usd is None:
            return False

        # 预算用完90%时降级
        usage_ratio = self.session_spent / self.session_prefs.session_budget_usd
        return usage_ratio >= 0.9


# ============================================================================
# Frontend Integration Example (修复版)
# ============================================================================

"""
前端集成示例（修复版）：

1. 创建Session时设置偏好（一次性）

```typescript
// 用户在设置页面选择模式
const createSession = async (mode: HybridMode) => {
  const response = await fetch('/api/v1/sessions', {
    method: 'POST',
    body: JSON.stringify({
      session_preferences: {
        mode: mode,  // "rule_only" | "conservative" | "balanced" | "aggressive"
        session_budget_usd: 0.10,  // $0.10预算
        budget_exceeded_action: "downgrade",  // 超出后降级
        user_id: currentUserId
      }
    })
  });

  const { session_id } = await response.json();
  return session_id;
};
```

2. 查询时不再传递偏好（从session读取）

```typescript
const query = async (question: string, sessionId: string) => {
  const response = await fetch('/api/v1/chat/query', {
    method: 'POST',
    body: JSON.stringify({
      question: question,
      session_id: sessionId,
      // 不再传 session_preferences！由后端从session中读取
      clarification_context: null  // 首次查询
    })
  });

  const data = await response.json();

  // 显示细粒度成本
  if (data.llm_calls.length > 0) {
    console.log('LLM调用详情:');
    data.llm_calls.forEach(call => {
      console.log(`  ${call.operation}: $${call.cost_usd.toFixed(6)} (${call.latency_ms}ms)`);
    });
  }

  // 显示预算状态
  if (data.session_budget_remaining !== null) {
    updateBudgetDisplay(data.session_budget_remaining);
    if (data.session_budget_remaining < 0.01) {
      showWarning('预算即将用完，将降级到免费模式');
    }
  }

  // 显示降级提示
  if (data.downgraded) {
    showNotification(`已降级到规则模式: ${data.downgrade_reason}`);
  }

  return data;
};
```

3. UI设计（修复版）

```html
<!-- Session创建页面 -->
<div class="create-session">
  <h3>创建新会话</h3>

  <!-- 模式选择 -->
  <div class="mode-selector">
    <label>
      <input type="radio" name="mode" value="rule_only" checked />
      <div class="mode-card">
        <h4>规则模式 ⚡</h4>
        <p>完全免费，<10ms响应</p>
        <span class="cost">$0.00/次</span>
      </div>
    </label>

    <label>
      <input type="radio" name="mode" value="conservative" />
      <div class="mode-card recommended">
        <h4>智能模式 💡 (推荐)</h4>
        <p>AI辅助，只在必要时调用</p>
        <span class="cost">~$0.0001/次</span>
      </div>
    </label>

    <label>
      <input type="radio" name="mode" value="aggressive" />
      <div class="mode-card">
        <h4>专业模式 🚀</h4>
        <p>最大化AI能力</p>
        <span class="cost">~$0.0003/次</span>
      </div>
    </label>
  </div>

  <!-- 预算设置 -->
  <div class="budget-setting" v-if="selectedMode !== 'rule_only'">
    <label>会话预算上限</label>
    <select v-model="sessionBudget">
      <option value="0.05">$0.05 (约50次查询)</option>
      <option value="0.10">$0.10 (约100次查询)</option>
      <option value="0.50">$0.50 (约500次查询)</option>
      <option value="1.00">$1.00 (最大)</option>
    </select>

    <label>预算用完时</label>
    <select v-model="budgetAction">
      <option value="downgrade">自动降级到免费模式</option>
      <option value="reject">停止响应，提示充值</option>
    </select>
  </div>

  <button @click="createSession">创建会话</button>
</div>

<!-- 查询界面 - 显示实时成本 -->
<div class="chat-interface">
  <div class="message assistant" v-if="response.llm_calls.length > 0">
    <div class="content">{{ response.question }}</div>
    <div class="metadata">
      <span class="badge-llm">AI 💡</span>
      <span class="cost">${{ response.total_cost_this_request.toFixed(6) }}</span>
      <details class="cost-details">
        <summary>查看详情</summary>
        <ul>
          <li v-for="call in response.llm_calls">
            {{ call.operation }}: ${{ call.cost_usd.toFixed(6) }} ({{ call.latency_ms }}ms)
          </li>
        </ul>
      </details>
    </div>
  </div>

  <!-- 预算进度条 -->
  <div class="budget-bar" v-if="response.session_budget_remaining !== null">
    <div class="progress" :style="{width: budgetUsedPercent + '%'}"></div>
    <span class="label">
      已用 ${{ response.session_total_cost.toFixed(4) }} /
      剩余 ${{ response.session_budget_remaining.toFixed(4) }}
    </span>
  </div>

  <!-- 降级提示 -->
  <div class="alert-warning" v-if="response.downgraded">
    ⚠️ {{ response.downgrade_reason }}
    <button @click="upgradeBudget">增加预算</button>
  </div>
</div>
```
"""


# ============================================================================
# Backend Implementation (伪代码)
# ============================================================================

"""
后端实现示例：

# app/api/routes/public/sessions.py

@router.post("/sessions")
async def create_session(request: CreateSessionRequest):
    # 后端强制验证预算限制
    if request.session_preferences.session_budget_usd is not None:
        if request.session_preferences.session_budget_usd > BudgetController.MAX_SESSION_BUDGET:
            raise HTTPException(400, "单session预算不能超过$1.00")

    # 创建session并保存偏好
    session = await session_service.create(
        preferences=request.session_preferences
    )

    return {"session_id": session.id}


# app/api/routes/public/chat.py

@router.post("/chat/query")
async def query(request: EnhancedQueryRequest):
    # 从DB读取session偏好（而非从请求）
    session = await session_service.get(request.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    prefs = session.preferences  # SessionClarificationPreferences

    # 初始化预算控制器
    budget = BudgetController(prefs)
    budget.session_spent = session.total_cost  # 从DB读取累计花费

    # 检查是否应该降级
    if budget.should_downgrade():
        # 临时降级到规则模式
        effective_mode = HybridMode.RULE_ONLY
        downgraded = True
        downgrade_reason = "预算即将用完，已自动降级到规则模式"
    else:
        effective_mode = prefs.mode
        downgraded = False
        downgrade_reason = None

    # 调用EnhancedRouterService（单一入口）
    router_service = EnhancedRouterService()
    result = await router_service.route_with_clarification(
        question=request.question,
        session_id=request.session_id,
        mode=effective_mode,  # 传递有效模式
        clarification_context=request.clarification_context,
        budget_controller=budget  # 传递预算控制器
    )

    # 更新session成本
    session.total_cost = budget.session_spent
    await session_service.update(session)

    # 构造响应
    response = ClarificationResponse(
        action=result.action,
        question=result.question,
        intent=result.intent,
        confidence=result.confidence,
        llm_calls=result.llm_calls,
        total_cost_this_request=sum(c.cost_usd for c in result.llm_calls),
        session_total_cost=session.total_cost,
        session_budget_remaining=(
            prefs.session_budget_usd - session.total_cost
            if prefs.session_budget_usd else None
        ),
        downgraded=downgraded,
        downgrade_reason=downgrade_reason
    )

    return response
"""
