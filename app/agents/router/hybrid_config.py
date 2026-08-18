"""
Enhanced Router Configuration - 混合策略配置

支持规则和LLM的混合使用：
- USE_HYBRID_CLARIFICATION: 是否启用混合模式
- LLM_FALLBACK_THRESHOLD: 规则置信度阈值，低于此值使用LLM
- LLM_ENHANCED_EXTRACTION: 是否使用LLM增强信息提取
"""

import os
from typing import Final

# ============================================================================
# Hybrid Clarification Configuration
# ============================================================================

# 启用混合澄清模式（规则 + LLM fallback）
USE_HYBRID_CLARIFICATION: Final[bool] = (
    os.getenv("USE_HYBRID_CLARIFICATION", "false").lower() == "true"
)

# LLM fallback阈值：规则置信度低于此值时使用LLM
# 建议值: 0.7-0.8（平衡速度和准确性）
LLM_FALLBACK_THRESHOLD: Final[float] = float(
    os.getenv("LLM_FALLBACK_THRESHOLD", "0.8")
)

# LLM增强信息提取：是否使用LLM辅助提取上下文信息
LLM_ENHANCED_EXTRACTION: Final[bool] = (
    os.getenv("LLM_ENHANCED_EXTRACTION", "false").lower() == "true"
)

# LLM动态问题生成：对于未定义的意图，是否使用LLM生成问题
LLM_DYNAMIC_QUESTIONS: Final[bool] = (
    os.getenv("LLM_DYNAMIC_QUESTIONS", "false").lower() == "true"
)

# ============================================================================
# Hybrid Mode Usage Examples
# ============================================================================

# Example 1: 纯规则模式（默认，最快）
# USE_HYBRID_CLARIFICATION=false
# → 只使用预定义规则和配置

# Example 2: 保守混合模式（推荐）
# USE_HYBRID_CLARIFICATION=true
# LLM_FALLBACK_THRESHOLD=0.8
# LLM_ENHANCED_EXTRACTION=false
# → 90%+ 场景用规则，只有低置信度case用LLM

# Example 3: 激进混合模式（最智能）
# USE_HYBRID_CLARIFICATION=true
# LLM_FALLBACK_THRESHOLD=0.7
# LLM_ENHANCED_EXTRACTION=true
# LLM_DYNAMIC_QUESTIONS=true
# → LLM深度参与，灵活性最高
