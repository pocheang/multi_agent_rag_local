# 增强Router实现方案

## 概述

将现有Router服务从**被动分类**升级为**主动澄清**，在路由决策前检查信息完整性，支持**动态轮次**（根据意图复杂度自动确定最大轮次，最多10轮）。

## 架构设计

### 设计原则

1. **选项B架构**：增强Router（澄清+分类合一）→ Planner
2. **向后兼容**：现有流程不受影响
3. **状态管理**：澄清上下文存储在会话历史中
4. **动态轮次**：根据意图复杂度自动确定最大轮次（2-10轮）
5. **历史提取**：从历史消息中智能提取已知信息

---

## 一、后端实现

### 1.1 核心数据结构

#### 文件: `app/domain/contracts.py`

```python
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

class RouterAction(str, Enum):
    """Router的决策动作"""
    CONTINUE = "CONTINUE"  # 信息充足，继续执行
    NEED_CLARIFICATION = "NEED_CLARIFICATION"  # 需要澄清

class ClarificationQuestion(BaseModel):
    """澄清问题结构"""
    question: str = Field(..., description="需要追问的问题")
    options: list[str] = Field(default_factory=list, description="提供的选项（2-5个）")
    allow_custom_input: bool = Field(default=True, description="是否允许自定义输入")
    field_name: str = Field(..., description="缺失信息的字段名，如'scenario'")

class ClarificationContext(BaseModel):
    """多轮澄清的上下文"""
    collected_info: dict[str, str] = Field(default_factory=dict, description="已收集的信息")
    asked_questions: list[str] = Field(default_factory=list, description="已询问的字段")
    clarification_round: int = Field(default=0, description="当前澄清轮次")
    max_rounds: int = Field(default=10, description="最大澄清轮次（动态设置）")
    intent: str = Field(default="", description="识别出的意图类型")

class EnhancedRouteDecision(BaseModel):
    """增强的路由决策"""
    # 原有字段
    intent: str
    route: str | None = None
    confidence: float
    requires_plan: bool
    allowed_capabilities: frozenset[str]
    reason: str
    
    # 新增字段
    action: RouterAction = RouterAction.CONTINUE
    missing_information: list[str] = Field(default_factory=list)
    clarification: ClarificationQuestion | None = None
    context: ClarificationContext = Field(default_factory=ClarificationContext)
```

#### 文件: `app/services/sessions/history.py`

在会话数据中增加clarification_context字段：

```python
# 修改create_session方法
def create_session(self, title: str | None = None, session_id: str | None = None) -> dict[str, Any]:
    session_id = validate_session_id(session_id) if session_id else uuid.uuid4().hex
    now = self._now()
    data = {
        "session_id": session_id,
        "title": title or DEFAULT_TITLE,
        "created_at": now,
        "updated_at": now,
        "messages": [],
        "runtime_policy": {"strategy_lock": None},
        "clarification_context": {  # 新增
            "collected_info": {},
            "asked_questions": [],
            "clarification_round": 0,
            "max_rounds": 10,  # 默认最大值，实际由意图决定
            "intent": ""
        }
    }
    with self._lock:
        self._write(session_id, data)
    return data

# 新增方法：更新澄清上下文
def update_clarification_context(
    self, 
    session_id: str, 
    field_name: str, 
    value: str
) -> dict[str, Any] | None:
    """更新会话的澄清上下文"""
    try:
        session_id = validate_session_id(session_id)
    except ValueError:
        return None
    
    with self._lock:
        data = self.get_session(session_id)
        if data is None:
            return None
        
        ctx = data.get("clarification_context", {})
        if not isinstance(ctx, dict):
            ctx = {
                "collected_info": {},
                "asked_questions": [],
                "clarification_round": 0,
                "max_rounds": 10,
                "intent": ""
            }
        
        # 更新收集的信息
        ctx.setdefault("collected_info", {})[field_name] = value
        
        # 记录已询问的字段
        if field_name not in ctx.get("asked_questions", []):
            ctx.setdefault("asked_questions", []).append(field_name)
        
        # 增加轮次
        ctx["clarification_round"] = ctx.get("clarification_round", 0) + 1
        
        data["clarification_context"] = ctx
        data["updated_at"] = self._now()
        self._write(session_id, data)
        return data

# 新增方法：重置澄清上下文
def reset_clarification_context(self, session_id: str) -> dict[str, Any] | None:
    """重置会话的澄清上下文（当进入CONTINUE阶段时调用）"""
    try:
        session_id = validate_session_id(session_id)
    except ValueError:
        return None
    
    with self._lock:
        data = self.get_session(session_id)
        if data is None:
            return None
        
        data["clarification_context"] = {
            "collected_info": {},
            "asked_questions": [],
            "clarification_round": 0,
            "max_rounds": 10,
            "intent": ""
        }
        data["updated_at"] = self._now()
        self._write(session_id, data)
        return data
```

### 1.2 增强Router服务

#### 文件: `app/agents/router/enhanced_service.py`

```python
"""增强的Router服务，支持信息完整性检查和主动澄清"""

import re
from typing import Any
from app.domain.contracts import (
    EnhancedRouteDecision, 
    RouterAction,
    ClarificationQuestion,
    ClarificationContext
)
from app.orchestration.request import OrchestrationRequest
from app.agents.router.service import RouterAgentService


# 意图复杂度配置（决定最大澄清轮次）
INTENT_COMPLEXITY = {
    "simple_query": 2,           # 简单查询：最多2轮
    "document_lookup": 3,        # 文档查找：最多3轮
    "document_comparison": 5,    # 文档对比：最多5轮
    "rag_design": 7,             # RAG设计：最多7轮（复杂）
    "system_architecture": 8,    # 系统架构：最多8轮
    "complex_analysis": 10,      # 复杂分析：最多10轮
    "default": 5,                # 默认：5轮
}

# 意图所需信息配置
INTENT_REQUIRED_INFO = {
    "rag_design": {
        "max_rounds": 7,  # 复杂意图，最多7轮
        "fields": ["scenario", "data_source", "scale", "performance_requirement"],
        "questions": {
            "scenario": ClarificationQuestion(
                question="这个 RAG 主要用于什么场景？",
                options=["企业知识库", "客服问答", "代码知识库", "数据分析"],
                allow_custom_input=True,
                field_name="scenario"
            ),
            "data_source": ClarificationQuestion(
                question="数据来源是什么类型？",
                options=["PDF文档", "数据库", "API接口", "网页爬取"],
                allow_custom_input=True,
                field_name="data_source"
            ),
            "scale": ClarificationQuestion(
                question="预计的数据规模大概有多大？",
                options=["小型（<1GB）", "中型（1-10GB）", "大型（10-100GB）", "超大型（>100GB）"],
                allow_custom_input=True,
                field_name="scale"
            ),
            "performance_requirement": ClarificationQuestion(
                question="对响应速度有什么要求？",
                options=["实时（<1秒）", "快速（1-3秒）", "一般（3-5秒）", "可接受（>5秒）"],
                allow_custom_input=True,
                field_name="performance_requirement"
            )
        }
    },
    "document_comparison": {
        "max_rounds": 5,  # 中等复杂度，最多5轮
        "fields": ["doc_ids", "comparison_aspect", "output_format"],
        "questions": {
            "doc_ids": ClarificationQuestion(
                question="需要比较哪些文档？",
                options=[],  # 动态从文档库加载
                allow_custom_input=True,
                field_name="doc_ids"
            ),
            "comparison_aspect": ClarificationQuestion(
                question="比较什么方面？",
                options=["价格", "功能", "性能", "时间"],
                allow_custom_input=True,
                field_name="comparison_aspect"
            ),
            "output_format": ClarificationQuestion(
                question="需要什么样的输出格式？",
                options=["对比表格", "详细报告", "简要总结", "可视化图表"],
                allow_custom_input=True,
                field_name="output_format"
            )
        }
    },
    "specific_query": {
        "max_rounds": 3,  # 简单查询，最多3轮
        "fields": ["entity", "attribute"],
        "questions": {
            "entity": ClarificationQuestion(
                question="你想查询哪个实体的信息？",
                options=[],  # 从上下文提取
                allow_custom_input=True,
                field_name="entity"
            ),
            "attribute": ClarificationQuestion(
                question="你想了解它的什么属性？",
                options=["价格", "规格", "日期", "数量"],
                allow_custom_input=True,
                field_name="attribute"
            )
        }
    }
}


class EnhancedRouterService:
    """增强的Router服务：澄清 + 分类"""
    
    def __init__(self, base_router: RouterAgentService | None = None):
        self.base_router = base_router or RouterAgentService()
    
    async def route(
        self, 
        request: OrchestrationRequest,
        clarification_context: ClarificationContext | None = None
    ) -> EnhancedRouteDecision:
        """
        执行增强路由决策
        
        1. 检查澄清上下文
        2. 分析意图
        3. 根据意图设置动态最大轮次
        4. 检查信息完整性
        5. 返回CONTINUE或NEED_CLARIFICATION
        """
        
        # 初始化上下文
        if clarification_context is None:
            clarification_context = ClarificationContext()
        
        # 从历史消息中提取已知信息
        extracted_info = self._extract_info_from_history(
            request.question,
            request.memory_context
        )
        
        # 合并已收集的信息和提取的信息
        all_known_info = {
            **clarification_context.collected_info,
            **extracted_info
        }
        
        # 识别意图
        intent = await self._identify_intent(request.question, all_known_info)
        
        # 动态设置最大轮次（根据意图复杂度）
        if not clarification_context.intent or clarification_context.intent != intent:
            clarification_context.intent = intent
            clarification_context.max_rounds = self._get_max_rounds_for_intent(intent)
        
        # 检查是否超过最大轮次
        if clarification_context.clarification_round >= clarification_context.max_rounds:
            # 超过最大轮次，强制继续（使用已有信息）
            base_decision = await self.base_router.route(request)
            return self._to_enhanced_decision(
                base_decision, 
                RouterAction.CONTINUE,
                clarification_context
            )
        
        # 从历史消息中提取已知信息
        extracted_info = self._extract_info_from_history(
            request.question,
            request.memory_context
        )
        
        # 合并已收集的信息和提取的信息
        all_known_info = {
            **clarification_context.collected_info,
            **extracted_info
        }
        
        # 识别意图
        intent = await self._identify_intent(request.question, all_known_info)
        
        # 检查简单问题（不需要澄清）
        if self._is_simple_query(request.question, intent):
            base_decision = await self.base_router.route(request)
            return self._to_enhanced_decision(
                base_decision,
                RouterAction.CONTINUE,
                clarification_context
            )
        
        # 检查信息完整性
        missing = self._check_missing_info(intent, all_known_info)
        
        if not missing:
            # 信息充足，继续执行
            base_decision = await self.base_router.route(request)
            return self._to_enhanced_decision(
                base_decision,
                RouterAction.CONTINUE,
                clarification_context
            )
        
        # 信息不足，选择下一个要问的问题
        next_question = self._select_next_question(
            intent,
            missing,
            clarification_context.asked_questions
        )
        
        if next_question is None:
            # 没有更多问题可问，强制继续
            base_decision = await self.base_router.route(request)
            return self._to_enhanced_decision(
                base_decision,
                RouterAction.CONTINUE,
                clarification_context
            )
        
        # 返回需要澄清
        base_decision = await self.base_router.route(request)
        return self._to_enhanced_decision(
            base_decision,
            RouterAction.NEED_CLARIFICATION,
            clarification_context,
            missing_information=missing,
            clarification=next_question
        )
    
    def _get_max_rounds_for_intent(self, intent: str) -> int:
        """根据意图获取最大轮次"""
        config = INTENT_REQUIRED_INFO.get(intent)
        if config and "max_rounds" in config:
            return config["max_rounds"]
        
        # 使用INTENT_COMPLEXITY作为fallback
        return INTENT_COMPLEXITY.get(intent, INTENT_COMPLEXITY["default"])
    
    def _extract_info_from_history(
        self, 
        current_question: str, 
        memory_context: str
    ) -> dict[str, str]:
        """从历史消息中提取已知信息"""
        extracted = {}
        
        # 场景识别
        scenario_patterns = {
            "企业知识库": r"企业|公司|组织|内部",
            "客服问答": r"客服|客户|服务|支持",
            "代码知识库": r"代码|编程|开发|技术文档",
            "数据分析": r"数据|分析|统计|报表"
        }
        
        text = current_question + " " + memory_context
        for scenario, pattern in scenario_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                extracted["scenario"] = scenario
                break
        
        # 数据源识别
        if "pdf" in text.lower() or "文档" in text:
            extracted["data_source"] = "PDF文档"
        elif "数据库" in text or "database" in text.lower():
            extracted["data_source"] = "数据库"
        
        return extracted
    
    async def _identify_intent(self, question: str, known_info: dict[str, str]) -> str:
        """识别用户意图"""
        question_lower = question.lower()
        
        # RAG设计意图
        if any(keyword in question for keyword in ["设计", "搭建", "构建", "实现"]) and \
           any(keyword in question for keyword in ["rag", "检索", "知识库"]):
            return "rag_design"
        
        # 文档比较意图
        if any(keyword in question for keyword in ["比较", "对比", "差异"]):
            return "document_comparison"
        
        # 特定查询意图
        if any(keyword in question for keyword in ["是什么", "有哪些", "什么时候"]):
            return "specific_query"
        
        # 默认为一般查询
        return "general_query"
    
    def _is_simple_query(self, question: str, intent: str) -> bool:
        """判断是否为简单问题（不需要澄清）"""
        
        # 一般查询不需要澄清
        if intent == "general_query":
            return True
        
        # 问题长度超过50字，认为信息充足
        if len(question) > 50:
            return True
        
        # 包含具体实体/数字/日期
        if re.search(r'\d+|具体的|明确的', question):
            return True
        
        return False
    
    def _check_missing_info(self, intent: str, known_info: dict[str, str]) -> list[str]:
        """检查缺失的信息"""
        config = INTENT_REQUIRED_INFO.get(intent)
        if config is None:
            return []
        
        required_fields = config["fields"]
        missing = []
        
        for field in required_fields:
            if field not in known_info or not known_info[field].strip():
                missing.append(field)
        
        return missing
    
    def _select_next_question(
        self,
        intent: str,
        missing_fields: list[str],
        asked_questions: list[str]
    ) -> ClarificationQuestion | None:
        """选择下一个要问的问题"""
        config = INTENT_REQUIRED_INFO.get(intent)
        if config is None:
            return None
        
        # 按优先级排序（第一个缺失的字段优先）
        for field in missing_fields:
            if field not in asked_questions:
                return config["questions"].get(field)
        
        return None
    
    def _to_enhanced_decision(
        self,
        base_decision: Any,
        action: RouterAction,
        context: ClarificationContext,
        missing_information: list[str] | None = None,
        clarification: ClarificationQuestion | None = None
    ) -> EnhancedRouteDecision:
        """转换为增强的路由决策"""
        return EnhancedRouteDecision(
            intent=base_decision.intent,
            route=base_decision.route,
            confidence=base_decision.confidence,
            requires_plan=base_decision.requires_plan,
            allowed_capabilities=base_decision.allowed_capabilities,
            reason=base_decision.reason,
            action=action,
            missing_information=missing_information or [],
            clarification=clarification,
            context=context
        )
```

### 1.3 API路由层修改

#### 文件: `app/api/routes/public/enhanced_query.py` (新增路由)

```python
"""增强查询路由，支持澄清流程"""

from fastapi import APIRouter, Depends, Request
from typing import Any
from pydantic import BaseModel

from app.api.dependencies import (
    _history_store_for_user,
    _require_user,
    _require_permission
)
from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext
from app.orchestration.request import OrchestrationRequest

router = APIRouter(prefix="/api/v1/clarification", tags=["clarification"])


class ClarificationRequest(BaseModel):
    """澄清请求"""
    question: str
    session_id: str
    field_name: str | None = None  # 用户回答的字段
    answer: str | None = None  # 用户的回答


class ClarificationResponse(BaseModel):
    """澄清响应"""
    action: str  # CONTINUE | NEED_CLARIFICATION
    clarification: dict[str, Any] | None = None
    context: dict[str, Any]
    route: dict[str, Any] | None = None


@router.post("/check", response_model=ClarificationResponse)
async def check_clarification(
    req: ClarificationRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user)
):
    """检查是否需要澄清"""
    _require_permission(user, "query:execute", request, "query")
    
    history_store = _history_store_for_user(user)
    session = history_store.get_session(req.session_id)
    
    if session is None:
        session = history_store.create_session(session_id=req.session_id)
    
    # 如果用户提供了答案，更新澄清上下文
    if req.field_name and req.answer:
        history_store.update_clarification_context(
            req.session_id,
            req.field_name,
            req.answer
        )
        session = history_store.get_session(req.session_id)
    
    # 获取澄清上下文
    ctx_data = session.get("clarification_context", {})
    context = ClarificationContext(**ctx_data)
    
    # 构建请求
    orchestration_req = OrchestrationRequest(
        question=req.question,
        session_id=req.session_id,
        memory_context="",  # TODO: 从历史消息构建
        use_reasoning=False,
        source_scope=None
    )
    
    # 执行增强路由
    router_service = EnhancedRouterService()
    decision = await router_service.route(orchestration_req, context)
    
    # 如果CONTINUE，重置澄清上下文
    if decision.action == "CONTINUE":
        history_store.reset_clarification_context(req.session_id)
    
    return ClarificationResponse(
        action=decision.action.value,
        clarification=decision.clarification.model_dump() if decision.clarification else None,
        context=decision.context.model_dump(),
        route={
            "intent": decision.intent,
            "route": decision.route,
            "confidence": decision.confidence
        } if decision.action == "CONTINUE" else None
    )
```

---

## 二、前端实现

### 2.1 类型定义

#### 文件: `frontend/src/types/api.ts`

```typescript
// 新增类型
export type RouterAction = "CONTINUE" | "NEED_CLARIFICATION";

export type ClarificationQuestion = {
  question: string;
  options: string[];
  allow_custom_input: boolean;
  field_name: string;
};

export type ClarificationContext = {
  collected_info: Record<string, string>;
  asked_questions: string[];
  clarification_round: number;
  max_rounds: number;
};

export type ClarificationCheckRequest = {
  question: string;
  session_id: string;
  field_name?: string;
  answer?: string;
};

export type ClarificationCheckResponse = {
  action: RouterAction;
  clarification: ClarificationQuestion | null;
  context: ClarificationContext;
  route: {
    intent: string;
    route: string | null;
    confidence: number;
  } | null;
};
```

### 2.2 API客户端

#### 文件: `frontend/src/services/api/chat.ts`

```typescript
// 在queryApi中添加
export const queryApi = {
  // ... 现有方法
  
  async checkClarification(
    request: ClarificationCheckRequest
  ): Promise<ClarificationCheckResponse> {
    const res = await authFetch("/api/v1/clarification/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    return parseOrThrow<ClarificationCheckResponse>(res);
  },
};
```

### 2.3 澄清UI组件

#### 文件: `frontend/src/pages/chat/components/ClarificationPrompt.tsx`

```typescript
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ClarificationQuestion, ClarificationContext } from "@/types/api";

type Props = {
  clarification: ClarificationQuestion;
  context: ClarificationContext;
  onAnswer: (fieldName: string, answer: string) => void;
  onCancel: () => void;
};

export function ClarificationPrompt({
  clarification,
  context,
  onAnswer,
  onCancel,
}: Props) {
  const { t } = useTranslation();
  const [selectedOption, setSelectedOption] = useState<string>("");
  const [customInput, setCustomInput] = useState<string>("");
  const [useCustom, setUseCustom] = useState<boolean>(false);

  const handleSubmit = () => {
    const answer = useCustom ? customInput : selectedOption;
    if (!answer.trim()) return;
    onAnswer(clarification.field_name, answer);
  };

  return (
    <div className="clarification-prompt">
      <div className="clarification-header">
        <h3>{t("components.chat.clarificationTitle")}</h3>
        <span className="clarification-round">
          {t("components.chat.clarificationRound", {
            current: context.clarification_round + 1,
            max: context.max_rounds,
          })}
        </span>
      </div>

      <p className="clarification-question">{clarification.question}</p>

      {/* 已收集信息展示 */}
      {Object.keys(context.collected_info).length > 0 && (
        <div className="collected-info">
          <h4>{t("components.chat.collectedInfo")}</h4>
          <ul>
            {Object.entries(context.collected_info).map(([key, value]) => (
              <li key={key}>
                <strong>{key}:</strong> {value}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 选项列表 */}
      {!useCustom && clarification.options.length > 0 && (
        <div className="clarification-options">
          {clarification.options.map((option) => (
            <button
              key={option}
              className={`option-btn ${selectedOption === option ? "selected" : ""}`}
              onClick={() => setSelectedOption(option)}
            >
              {option}
            </button>
          ))}
        </div>
      )}

      {/* 自定义输入 */}
      {clarification.allow_custom_input && (
        <>
          {!useCustom && clarification.options.length > 0 && (
            <button
              className="use-custom-btn"
              onClick={() => setUseCustom(true)}
            >
              {t("components.chat.useCustomInput")}
            </button>
          )}
          
          {(useCustom || clarification.options.length === 0) && (
            <div className="custom-input-wrapper">
              <textarea
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                placeholder={t("components.chat.customInputPlaceholder")}
                rows={3}
              />
              {useCustom && clarification.options.length > 0 && (
                <button
                  className="back-to-options-btn"
                  onClick={() => {
                    setUseCustom(false);
                    setCustomInput("");
                  }}
                >
                  {t("components.chat.backToOptions")}
                </button>
              )}
            </div>
          )}
        </>
      )}

      <div className="clarification-actions">
        <button className="cancel-btn" onClick={onCancel}>
          {t("common.cancel")}
        </button>
        <button
          className="submit-btn"
          onClick={handleSubmit}
          disabled={!selectedOption && !customInput.trim()}
        >
          {t("common.submit")}
        </button>
      </div>
    </div>
  );
}
```

### 2.4 Chat页面集成

#### 文件: `frontend/src/pages/chat/hooks/useChatActions.ts`

```typescript
// 添加新的action
const actions = {
  // ... 现有actions
  
  async checkClarification(
    question: string,
    sessionId: string,
    fieldName?: string,
    answer?: string
  ) {
    try {
      const response = await queryApi.checkClarification({
        question,
        session_id: sessionId,
        field_name: fieldName,
        answer: answer,
      });
      return response;
    } catch (error) {
      notify(t("errors.clarificationFailed"), "error");
      throw error;
    }
  },
};
```

#### 文件: `frontend/src/pages/ChatPage.tsx`

在状态中添加：

```typescript
const [clarificationState, setClarificationState] = useState<{
  active: boolean;
  clarification: ClarificationQuestion | null;
  context: ClarificationContext | null;
}>({
  active: false,
  clarification: null,
  context: null,
});
```

在提交问题时的逻辑：

```typescript
const handleAsk = async () => {
  if (!question.trim() || !currentSessionId) return;
  
  setIsSending(true);
  
  try {
    // 1. 先检查是否需要澄清
    const checkResult = await actions.checkClarification(
      question,
      currentSessionId
    );
    
    if (checkResult.action === "NEED_CLARIFICATION") {
      // 需要澄清，显示澄清界面
      setClarificationState({
        active: true,
        clarification: checkResult.clarification,
        context: checkResult.context,
      });
      setIsSending(false);
      return;
    }
    
    // 2. 信息充足，继续执行查询
    await messageActions.ask({
      question,
      isSending,
      useWeb,
      useReasoning,
      agentClassHint,
      retrievalStrategy,
      pipelineProfile,
    });
    
  } catch (error) {
    console.error("Ask failed:", error);
    setError(String(error));
  } finally {
    setIsSending(false);
  }
};

const handleClarificationAnswer = async (fieldName: string, answer: string) => {
  if (!currentSessionId) return;
  
  try {
    // 提交答案并重新检查
    const checkResult = await actions.checkClarification(
      question,
      currentSessionId,
      fieldName,
      answer
    );
    
    if (checkResult.action === "NEED_CLARIFICATION") {
      // 还需要继续澄清
      setClarificationState({
        active: true,
        clarification: checkResult.clarification,
        context: checkResult.context,
      });
    } else {
      // 澄清完成，执行查询
      setClarificationState({
        active: false,
        clarification: null,
        context: null,
      });
      
      await messageActions.ask({
        question,
        isSending,
        useWeb,
        useReasoning,
        agentClassHint,
        retrievalStrategy,
        pipelineProfile,
      });
    }
  } catch (error) {
    console.error("Clarification answer failed:", error);
  }
};
```

在渲染中添加：

```typescript
<main className="main">
  {clarificationState.active && clarificationState.clarification ? (
    <ClarificationPrompt
      clarification={clarificationState.clarification}
      context={clarificationState.context!}
      onAnswer={handleClarificationAnswer}
      onCancel={() => {
        setClarificationState({
          active: false,
          clarification: null,
          context: null,
        });
        setIsSending(false);
      }}
    />
  ) : (
    <>
      <ChatMessages ... />
      <ChatComposer ... />
    </>
  )}
</main>
```

### 2.5 样式

#### 文件: `frontend/src/styles/components/clarification.css`

```css
.clarification-prompt {
  max-width: 600px;
  margin: 2rem auto;
  padding: 2rem;
  background: var(--bg-secondary);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.clarification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.clarification-header h3 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
}

.clarification-round {
  font-size: 0.875rem;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
}

.clarification-question {
  font-size: 1.125rem;
  margin-bottom: 1.5rem;
  color: var(--text-primary);
}

.collected-info {
  background: var(--bg-tertiary);
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
}

.collected-info h4 {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  color: var(--text-secondary);
}

.collected-info ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.collected-info li {
  font-size: 0.875rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.collected-info li:last-child {
  border-bottom: none;
}

.collected-info strong {
  color: var(--text-primary);
  margin-right: 0.5rem;
}

.clarification-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.option-btn {
  padding: 0.75rem 1rem;
  border: 2px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.9375rem;
  cursor: pointer;
  transition: all 0.2s;
}

.option-btn:hover {
  border-color: var(--primary-color);
  background: var(--primary-bg-hover);
}

.option-btn.selected {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: white;
}

.use-custom-btn,
.back-to-options-btn {
  width: 100%;
  padding: 0.75rem;
  margin-bottom: 1rem;
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.use-custom-btn:hover,
.back-to-options-btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.custom-input-wrapper textarea {
  width: 100%;
  padding: 0.75rem;
  border: 2px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.9375rem;
  font-family: inherit;
  resize: vertical;
  margin-bottom: 0.75rem;
}

.custom-input-wrapper textarea:focus {
  outline: none;
  border-color: var(--primary-color);
}

.clarification-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

.clarification-actions button {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-size: 0.9375rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.cancel-btn:hover {
  background: var(--bg-hover);
}

.submit-btn {
  background: var(--primary-color);
  color: white;
}

.submit-btn:hover:not(:disabled) {
  background: var(--primary-hover);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

---

## 三、测试计划

### 3.1 单元测试

#### 文件: `tests/agents/router/test_enhanced_service.py`

```python
import pytest
from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext, RouterAction
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_simple_query_continues():
    """简单问题应该直接CONTINUE"""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="这个产品的价格是多少？",
        session_id="test",
        memory_context="",
        use_reasoning=False
    )
    
    decision = await service.route(request)
    assert decision.action == RouterAction.CONTINUE


@pytest.mark.asyncio
async def test_ambiguous_query_needs_clarification():
    """模糊问题应该请求澄清"""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="帮我设计一个RAG",
        session_id="test",
        memory_context="",
        use_reasoning=False
    )
    
    decision = await service.route(request)
    assert decision.action == RouterAction.NEED_CLARIFICATION
    assert decision.clarification is not None
    assert decision.clarification.field_name in ["scenario", "data_source"]


@pytest.mark.asyncio
async def test_multi_round_clarification():
    """测试多轮澄清"""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="帮我设计一个RAG",
        session_id="test",
        memory_context="",
        use_reasoning=False
    )
    
    # 第一轮
    context = ClarificationContext()
    decision1 = await service.route(request, context)
    assert decision1.action == RouterAction.NEED_CLARIFICATION
    
    # 模拟用户回答
    context.collected_info["scenario"] = "企业知识库"
    context.clarification_round = 1
    context.asked_questions.append("scenario")
    
    # 第二轮
    decision2 = await service.route(request, context)
    assert decision2.action == RouterAction.NEED_CLARIFICATION
    assert decision2.clarification.field_name == "data_source"
    
    # 模拟第二次回答
    context.collected_info["data_source"] = "PDF文档"
    context.clarification_round = 2
    context.asked_questions.append("data_source")
    
    # 第三轮应该CONTINUE
    decision3 = await service.route(request, context)
    assert decision3.action == RouterAction.CONTINUE


@pytest.mark.asyncio
async def test_max_rounds_limit():
    """测试最大轮次限制"""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="帮我设计一个RAG",
        session_id="test",
        memory_context="",
        use_reasoning=False
    )
    
    context = ClarificationContext(clarification_round=5, max_rounds=5)
    decision = await service.route(request, context)
    
    # 超过最大轮次应该强制CONTINUE
    assert decision.action == RouterAction.CONTINUE


@pytest.mark.asyncio
async def test_info_extraction_from_history():
    """测试从历史消息提取信息"""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="我想继续之前的RAG项目",
        session_id="test",
        memory_context="用户之前提到要做企业知识库，数据来源是PDF文档",
        use_reasoning=False
    )
    
    context = ClarificationContext()
    decision = await service.route(request, context)
    
    # 应该从历史中提取到信息，不需要再问
    assert decision.action == RouterAction.CONTINUE
```

### 3.2 集成测试

#### 文件: `tests/integration/test_clarification_flow.py`

```python
import pytest
from fastapi.testclient import TestClient
from app.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_clarification_flow_end_to_end(client):
    """端到端澄清流程测试"""
    
    # 1. 创建会话
    response = client.post("/sessions")
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    
    # 2. 第一次提问（触发澄清）
    response = client.post("/api/v1/clarification/check", json={
        "question": "帮我设计一个RAG",
        "session_id": session_id
    })
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "NEED_CLARIFICATION"
    assert data["clarification"]["field_name"] == "scenario"
    
    # 3. 回答第一个问题
    response = client.post("/api/v1/clarification/check", json={
        "question": "帮我设计一个RAG",
        "session_id": session_id,
        "field_name": "scenario",
        "answer": "企业知识库"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "NEED_CLARIFICATION"
    assert data["clarification"]["field_name"] == "data_source"
    assert data["context"]["collected_info"]["scenario"] == "企业知识库"
    
    # 4. 回答第二个问题
    response = client.post("/api/v1/clarification/check", json={
        "question": "帮我设计一个RAG",
        "session_id": session_id,
        "field_name": "data_source",
        "answer": "PDF文档"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "CONTINUE"
    assert data["route"] is not None
    assert data["context"]["collected_info"]["data_source"] == "PDF文档"
```

---

## 四、国际化

#### 文件: `frontend/src/i18n/locales/zh.json`

```json
{
  "components": {
    "chat": {
      "clarificationTitle": "需要更多信息",
      "clarificationRound": "第 {{current}}/{{max}} 轮",
      "collectedInfo": "已收集信息",
      "useCustomInput": "自定义输入",
      "customInputPlaceholder": "请输入您的答案...",
      "backToOptions": "返回选项"
    }
  },
  "errors": {
    "clarificationFailed": "澄清检查失败"
  }
}
```

#### 文件: `frontend/src/i18n/locales/en.json`

```json
{
  "components": {
    "chat": {
      "clarificationTitle": "Need More Information",
      "clarificationRound": "Round {{current}}/{{max}}",
      "collectedInfo": "Collected Information",
      "useCustomInput": "Custom Input",
      "customInputPlaceholder": "Enter your answer...",
      "backToOptions": "Back to Options"
    }
  },
  "errors": {
    "clarificationFailed": "Clarification check failed"
  }
}
```

---

## 五、迁移路径

### 阶段1: 后端核心 (P0)
1. 新增数据结构到 `app/domain/contracts.py`
2. 实现 `EnhancedRouterService`
3. 更新 `HistoryStore` 支持澄清上下文
4. 新增 `/api/v1/clarification/check` 路由
5. 单元测试

### 阶段2: 前端UI (P0)
1. 新增类型定义
2. 实现 `ClarificationPrompt` 组件
3. 更新 `ChatPage` 集成澄清流程
4. 样式实现
5. 国际化

### 阶段3: 集成优化 (P1)
1. 与OrchestrationEngine集成
2. 历史消息智能提取
3. 动态选项生成（从文档库）
4. 集成测试

### 阶段4: 体验优化 (P2)
1. 澄清历史可视化
2. 撤销上一轮澄清
3. 保存澄清模板
4. 智能推荐选项

---

## 六、性能考虑

1. **缓存**: 意图识别结果缓存（同一session_id + question组合）
2. **并发**: 澄清检查与主查询分离，避免阻塞
3. **超时**: 澄清检查设置2秒超时，超时直接CONTINUE
4. **限流**: 每个会话最多5轮澄清，防止无限循环

---

## 七、监控指标

1. **澄清触发率**: 需要澄清的问题占比
2. **澄清完成率**: 完成澄清流程的占比
3. **平均澄清轮次**: 平均需要几轮澄清
4. **澄清放弃率**: 用户取消澄清的占比
5. **信息提取准确率**: 从历史消息提取信息的准确率

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 澄清过度，影响用户体验 | 高 | 1. 智能判断简单问题 2. 限制最多5轮 3. 允许跳过 |
| 历史提取不准确 | 中 | 1. 保守提取策略 2. 用户可修正 3. 记录提取日志 |
| 前端状态管理复杂 | 中 | 1. 使用独立状态 2. 清晰的状态转换 3. 完善的测试 |
| 向后兼容性问题 | 低 | 1. 独立路由 2. 现有流程不变 3. 渐进式迁移 |

---

## 九、未来扩展

1. **智能选项生成**: 根据文档库动态生成选项
2. **多模态澄清**: 支持图片、表格等
3. **澄清模板**: 保存常用澄清模板
4. **批量澄清**: 一次询问多个问题
5. **智能推荐**: 基于历史会话推荐答案
6. **语音澄清**: 支持语音输入回答

---

## 十、文档更新

需要更新的文档：
1. `CLAUDE.md` - 添加澄清功能说明
2. `README.md` - 更新功能列表
3. API文档 - 新增澄清相关接口
4. 用户手册 - 澄清功能使用指南

---

## 总结

这个实现方案提供了：
- ✅ **完整的后端架构**: 数据结构、服务层、API路由
- ✅ **完整的前端UI**: 组件、状态管理、样式
- ✅ **测试策略**: 单元测试、集成测试
- ✅ **渐进式迁移**: 不破坏现有功能
- ✅ **可扩展性**: 易于添加新的意图和问题

实施顺序：后端核心 → 前端UI → 集成测试 → 优化迭代
