"""
AI辅助报告编辑功能 (AI-Assisted Report Editing)

核心功能：
1. AI润色 - 改进语言表达，使其更专业
2. AI扩展 - 扩充内容，增加细节
3. AI总结 - 提炼核心要点
4. AI重写 - 按指定风格重写
5. AI补全 - 自动补充缺失部分
6. 自定义指令 - 用户自定义编辑要求
"""

from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.services.models.runtime import get_chat_model

logger = logging.getLogger(__name__)

# ============================================================================
# AI编辑操作类型
# ============================================================================

AIEditOperation = Literal[
    "polish",  # 润色
    "expand",  # 扩展
    "summarize",  # 总结
    "rewrite",  # 重写
    "complete",  # 补全
    "translate",  # 翻译
    "custom",  # 自定义
]


# ============================================================================
# 请求/响应模型
# ============================================================================


class AIEditRequest(BaseModel):
    """AI编辑请求"""

    operation: AIEditOperation = Field(..., description="编辑操作类型")
    content: str = Field(..., description="要编辑的内容")
    instruction: str = Field(default="", description="自定义指令（operation=custom时必填）")
    context: str = Field(default="", description="上下文信息（可选）")
    style: str = Field(default="professional", description="风格：professional/casual/technical/executive")
    language: str = Field(default="zh", description="语言：zh/en")


class AIEditResponse(BaseModel):
    """AI编辑响应"""

    original: str = Field(..., description="原始内容")
    edited: str = Field(..., description="编辑后内容")
    operation: str = Field(..., description="执行的操作")
    changes_summary: str = Field(default="", description="修改摘要")


# ============================================================================
# AI编辑提示词
# ============================================================================

POLISH_SYSTEM_PROMPT = """你是一位专业的文字编辑，擅长润色和改进文本表达。

**你的任务**：
- 改进语言表达，使其更清晰、流畅、专业
- 修正语法错误和拼写错误
- 优化句子结构，提升可读性
- 保持原意不变
- 保留专业术语和关键信息

**润色原则**：
1. 清晰性 - 表达清晰明了，避免歧义
2. 专业性 - 使用恰当的专业术语
3. 简洁性 - 删除冗余，保持简洁
4. 逻辑性 - 确保逻辑连贯
5. 准确性 - 保持事实准确

**输出格式**：
只输出润色后的文本，不要添加任何解释或说明。"""

EXPAND_SYSTEM_PROMPT = """你是一位内容创作专家，擅长扩展和丰富内容。

**你的任务**：
- 在保持原意的基础上扩展内容
- 添加更多细节、例子和说明
- 深化论述，增加深度
- 保持逻辑连贯性
- 适当增加段落和结构

**扩展策略**：
1. 添加背景信息和上下文
2. 提供具体例子和案例
3. 深入解释原理和机制
4. 补充相关数据和统计
5. 增加实践指导和建议

**扩展比例**：
- 将内容扩展到原来的1.5-2倍
- 保持核心观点不变
- 确保新增内容有价值

**输出格式**：
只输出扩展后的文本，不要添加任何解释或说明。"""

SUMMARIZE_SYSTEM_PROMPT = """你是一位总结专家，擅长提炼核心要点。

**你的任务**：
- 提炼核心观点和关键信息
- 删除次要细节和冗余内容
- 保持逻辑结构清晰
- 确保关键信息不丢失

**总结原则**：
1. 完整性 - 涵盖所有核心要点
2. 简洁性 - 删除冗余和细节
3. 准确性 - 忠实于原文
4. 可读性 - 流畅易懂
5. 结构性 - 保持逻辑结构

**总结长度**：
- 控制在原文的30-40%
- 保留最重要的信息
- 使用简洁的语言

**输出格式**：
只输出总结后的文本，不要添加任何解释或说明。"""

REWRITE_SYSTEM_PROMPT_TEMPLATE = """你是一位写作专家，擅长用不同风格重写内容。

**你的任务**：
- 用{style}风格重写内容
- 保持核心信息不变
- 适应目标受众
- 调整语气和措辞

**风格定义**：

**Professional（专业）**：
- 正式、严谨、客观
- 使用专业术语
- 结构化表达
- 适合商务报告、技术文档

**Casual（随意）**：
- 轻松、友好、口语化
- 简单易懂
- 生动有趣
- 适合博客、社交媒体

**Technical（技术）**：
- 精确、详细、专业
- 大量技术术语
- 逻辑严密
- 适合技术文档、API文档

**Executive（高管）**：
- 简洁、直接、高层次
- 强调结果和影响
- 战略性视角
- 适合管理层汇报

**输出格式**：
只输出重写后的文本，不要添加任何解释或说明。"""

COMPLETE_SYSTEM_PROMPT = """你是一位内容补全专家，擅长续写和补充内容。

**你的任务**：
- 分析现有内容的结构和方向
- 补充缺失的部分
- 确保内容完整性
- 保持风格和语气一致

**补全策略**：
1. 理解上下文和意图
2. 识别缺失的关键部分
3. 补充必要的信息
4. 保持逻辑连贯
5. 与原文风格一致

**补全原则**：
- 只补充必要的内容
- 不重复已有信息
- 保持专业性
- 确保准确性

**输出格式**：
只输出补全后的完整文本，不要添加任何解释或说明。"""

TRANSLATE_SYSTEM_PROMPT_TEMPLATE = """你是一位专业翻译，擅长技术文档翻译。

**你的任务**：
- 将内容翻译为{target_language}
- 保持专业术语准确
- 保留格式和结构
- 确保表达自然流畅

**翻译原则**：
1. 准确性 - 忠实原文意思
2. 专业性 - 正确翻译术语
3. 流畅性 - 表达自然地道
4. 完整性 - 不遗漏信息
5. 一致性 - 术语翻译一致

**注意事项**：
- 保留Markdown格式
- 保留代码块不翻译
- 保留专有名词
- 保留链接和引用

**输出格式**：
只输出翻译后的文本，不要添加任何解释或说明。"""


# ============================================================================
# AI编辑器
# ============================================================================


class AIReportEditor:
    """AI报告编辑器"""

    def __init__(self):
        self.model = get_chat_model()

    async def edit(self, request: AIEditRequest) -> AIEditResponse:
        """
        执行AI编辑操作

        Args:
            request: 编辑请求

        Returns:
            编辑响应
        """
        # 根据操作类型选择提示词
        if request.operation == "polish":
            system_prompt = POLISH_SYSTEM_PROMPT
            user_prompt = self._build_polish_prompt(request)

        elif request.operation == "expand":
            system_prompt = EXPAND_SYSTEM_PROMPT
            user_prompt = self._build_expand_prompt(request)

        elif request.operation == "summarize":
            system_prompt = SUMMARIZE_SYSTEM_PROMPT
            user_prompt = self._build_summarize_prompt(request)

        elif request.operation == "rewrite":
            system_prompt = REWRITE_SYSTEM_PROMPT_TEMPLATE.format(style=self._get_style_name(request.style))
            user_prompt = self._build_rewrite_prompt(request)

        elif request.operation == "complete":
            system_prompt = COMPLETE_SYSTEM_PROMPT
            user_prompt = self._build_complete_prompt(request)

        elif request.operation == "translate":
            target_lang = "English" if request.language == "en" else "中文"
            system_prompt = TRANSLATE_SYSTEM_PROMPT_TEMPLATE.format(target_language=target_lang)
            user_prompt = self._build_translate_prompt(request)

        elif request.operation == "custom":
            system_prompt = "你是一位专业的文字编辑，请按照用户的要求编辑内容。"
            user_prompt = self._build_custom_prompt(request)

        else:
            raise ValueError(f"Unsupported operation: {request.operation}")

        # 调用LLM
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

        response = await self.model.ainvoke(messages)
        edited_content = response.content.strip()

        # 生成修改摘要
        changes_summary = self._generate_changes_summary(request, edited_content)

        return AIEditResponse(
            original=request.content,
            edited=edited_content,
            operation=request.operation,
            changes_summary=changes_summary,
        )

    def _build_polish_prompt(self, request: AIEditRequest) -> str:
        """构建润色提示词"""
        prompt_parts = []

        if request.language == "zh":
            prompt_parts.append("请润色以下中文内容：\n\n")
        else:
            prompt_parts.append("Please polish the following English content:\n\n")

        prompt_parts.append(f"【原文】\n{request.content}\n\n")

        if request.context:
            prompt_parts.append(f"【上下文】\n{request.context}\n\n")

        if request.language == "zh":
            prompt_parts.append("【要求】\n- 使用专业的语言\n- 保持原意不变\n- 提升可读性")
        else:
            prompt_parts.append(
                "【Requirements】\n- Use professional language\n- Keep original meaning\n- Improve readability"
            )

        return "".join(prompt_parts)

    def _build_expand_prompt(self, request: AIEditRequest) -> str:
        """构建扩展提示词"""
        prompt_parts = []

        if request.language == "zh":
            prompt_parts.append("请扩展以下内容，增加细节和深度：\n\n")
        else:
            prompt_parts.append("Please expand the following content with more details:\n\n")

        prompt_parts.append(f"【原文】\n{request.content}\n\n")

        if request.context:
            prompt_parts.append(f"【上下文】\n{request.context}\n\n")

        if request.language == "zh":
            prompt_parts.append("【要求】\n- 扩展到1.5-2倍长度\n- 添加例子和细节\n- 保持核心观点不变")
        else:
            prompt_parts.append(
                "【Requirements】\n- Expand to 1.5-2x length\n- Add examples and details\n- Keep core points unchanged"
            )

        return "".join(prompt_parts)

    def _build_summarize_prompt(self, request: AIEditRequest) -> str:
        """构建总结提示词"""
        prompt_parts = []

        if request.language == "zh":
            prompt_parts.append("请总结以下内容，提炼核心要点：\n\n")
        else:
            prompt_parts.append("Please summarize the following content:\n\n")

        prompt_parts.append(f"【原文】\n{request.content}\n\n")

        if request.language == "zh":
            prompt_parts.append("【要求】\n- 控制在原文30-40%长度\n- 保留关键信息\n- 删除冗余细节")
        else:
            prompt_parts.append(
                "【Requirements】\n- Keep 30-40% of original length\n- Retain key information\n- Remove redundant details"
            )

        return "".join(prompt_parts)

    def _build_rewrite_prompt(self, request: AIEditRequest) -> str:
        """构建重写提示词"""
        style_name = self._get_style_name(request.style)

        prompt_parts = []

        if request.language == "zh":
            prompt_parts.append(f"请用{style_name}风格重写以下内容：\n\n")
        else:
            prompt_parts.append(f"Please rewrite the following content in {style_name} style:\n\n")

        prompt_parts.append(f"【原文】\n{request.content}\n\n")

        if request.context:
            prompt_parts.append(f"【上下文】\n{request.context}\n\n")

        return "".join(prompt_parts)

    def _build_complete_prompt(self, request: AIEditRequest) -> str:
        """构建补全提示词"""
        prompt_parts = []

        if request.language == "zh":
            prompt_parts.append("以下内容不完整，请补充缺失的部分：\n\n")
        else:
            prompt_parts.append("The following content is incomplete. Please complete it:\n\n")

        prompt_parts.append(f"【原文】\n{request.content}\n\n")

        if request.context:
            prompt_parts.append(f"【上下文】\n{request.context}\n\n")

        if request.language == "zh":
            prompt_parts.append("【要求】\n- 补充缺失的关键部分\n- 保持风格一致\n- 确保内容完整")
        else:
            prompt_parts.append(
                "【Requirements】\n- Complete missing key parts\n- Keep consistent style\n- Ensure completeness"
            )

        return "".join(prompt_parts)

    def _build_translate_prompt(self, request: AIEditRequest) -> str:
        """构建翻译提示词"""
        target_lang = "English" if request.language == "en" else "中文"

        prompt_parts = [
            f"请将以下内容翻译为{target_lang}：\n\n",
            f"【原文】\n{request.content}\n\n",
        ]

        if request.context:
            prompt_parts.append(f"【上下文】\n{request.context}\n\n")

        return "".join(prompt_parts)

    def _build_custom_prompt(self, request: AIEditRequest) -> str:
        """构建自定义提示词"""
        prompt_parts = [
            f"【用户要求】\n{request.instruction}\n\n",
            f"【内容】\n{request.content}\n\n",
        ]

        if request.context:
            prompt_parts.append(f"【上下文】\n{request.context}\n\n")

        return "".join(prompt_parts)

    def _get_style_name(self, style: str) -> str:
        """获取风格名称"""
        style_names = {
            "professional": "专业",
            "casual": "随意",
            "technical": "技术",
            "executive": "高管",
        }
        return style_names.get(style, "专业")

    def _generate_changes_summary(self, request: AIEditRequest, edited: str) -> str:
        """生成修改摘要"""
        original_len = len(request.content)
        edited_len = len(edited)
        change_ratio = ((edited_len - original_len) / original_len * 100) if original_len > 0 else 0

        operation_names = {
            "polish": "润色",
            "expand": "扩展",
            "summarize": "总结",
            "rewrite": "重写",
            "complete": "补全",
            "translate": "翻译",
            "custom": "自定义编辑",
        }

        operation_name = operation_names.get(request.operation, request.operation)

        if change_ratio > 10:
            return f"{operation_name}：内容增加了{change_ratio:.0f}%"
        elif change_ratio < -10:
            return f"{operation_name}：内容减少了{abs(change_ratio):.0f}%"
        else:
            return f"{operation_name}：内容长度基本不变"


# ============================================================================
# 全局实例
# ============================================================================

_ai_editor: AIReportEditor | None = None


def get_ai_report_editor() -> AIReportEditor:
    """获取AI报告编辑器实例（单例）"""
    global _ai_editor
    if _ai_editor is None:
        _ai_editor = AIReportEditor()
    return _ai_editor
