"""Synonym expansion service for Chinese query enhancement."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SynonymExpander:
    """Expands queries with synonyms to improve recall."""

    def __init__(self, synonym_dict_path: str | None = None):
        """Initialize the synonym expander.

        Args:
            synonym_dict_path: Path to JSON file containing synonym mappings
        """
        self.synonyms: dict[str, set[str]] = {}

        if synonym_dict_path:
            self.load_synonyms(synonym_dict_path)
        else:
            self._load_default_synonyms()

    def _load_default_synonyms(self):
        """Load default Chinese synonyms for common technical and business terms."""
        default_synonyms = {
            # Technical terms
            "人工智能": {"AI", "机器学习", "深度学习"},
            "机器学习": {"AI", "人工智能", "ML"},
            "深度学习": {"神经网络", "DL", "人工智能"},
            "数据库": {"DB", "数据存储", "数据仓库"},
            "服务器": {"主机", "云服务器", "计算节点"},
            "网络": {"互联网", "局域网", "网路"},
            "安全": {"信息安全", "网络安全", "安全性"},
            "性能": {"效能", "表现", "性能指标"},
            "优化": {"改进", "提升", "增强"},
            "系统": {"平台", "框架", "体系"},
            # Business terms
            "员工": {"职工", "雇员", "人员"},
            "公司": {"企业", "组织", "机构"},
            "管理": {"管控", "治理", "监管"},
            "流程": {"过程", "程序", "步骤"},
            "政策": {"制度", "规定", "方针"},
            "报销": {"费用报销", "财务报销", "开支报销"},
            "假期": {"休假", "请假", "年假"},
            "薪资": {"工资", "薪水", "报酬"},
            "培训": {"训练", "学习", "教育"},
            "考核": {"评估", "评价", "考评"},
            # Common verbs
            "使用": {"应用", "运用", "采用"},
            "创建": {"建立", "创造", "生成"},
            "删除": {"移除", "清除", "去除"},
            "修改": {"更改", "变更", "编辑"},
            "查询": {"检索", "搜索", "查找"},
            "提交": {"递交", "上传", "发送"},
            "审批": {"审核", "批准", "核准"},
            "配置": {"设置", "设定", "配备"},
            # Common adjectives
            "重要": {"关键", "核心", "主要"},
            "简单": {"容易", "简易", "轻松"},
            "复杂": {"困难", "繁琐", "麻烦"},
            "快速": {"迅速", "高效", "敏捷"},
            "安全": {"可靠", "稳定", "保险"},
        }

        self.synonyms = {k: set(v) for k, v in default_synonyms.items()}
        logger.info(f"Loaded {len(self.synonyms)} default synonym groups")

    def load_synonyms(self, file_path: str):
        """Load synonyms from a JSON file.

        Expected format:
        {
            "word1": ["syn1", "syn2"],
            "word2": ["syn3", "syn4"]
        }

        Args:
            file_path: Path to synonym dictionary JSON file
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Synonym file not found: {file_path}")
                self._load_default_synonyms()
                return

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            self.synonyms = {k: set(v) for k, v in data.items()}
            logger.info(f"Loaded {len(self.synonyms)} synonym groups from {file_path}")

        except Exception as e:
            logger.error(f"Failed to load synonyms from {file_path}: {e}")
            self._load_default_synonyms()

    def add_synonym_group(self, word: str, synonyms: set[str]):
        """Add a synonym group.

        Args:
            word: The main word
            synonyms: Set of synonyms for the word
        """
        if word in self.synonyms:
            self.synonyms[word].update(synonyms)
        else:
            self.synonyms[word] = set(synonyms)

        logger.debug(f"Added synonym group for '{word}': {synonyms}")

    def get_synonyms(self, word: str) -> set[str]:
        """Get synonyms for a word.

        Args:
            word: The word to find synonyms for

        Returns:
            Set of synonyms (empty if none found)
        """
        return self.synonyms.get(word, set())

    def expand_query(self, tokens: list[str], max_expansions: int = 2) -> list[str]:
        """Expand query tokens with synonyms.

        Args:
            tokens: List of query tokens
            max_expansions: Maximum number of synonyms to add per token

        Returns:
            Expanded list of tokens (original + synonyms)
        """
        expanded = list(tokens)  # Start with original tokens

        for token in tokens:
            synonyms = self.get_synonyms(token)
            if synonyms:
                # Add up to max_expansions synonyms
                expanded.extend(list(synonyms)[:max_expansions])
                logger.debug(f"Expanded '{token}' with: {list(synonyms)[:max_expansions]}")

        return expanded

    def expand_query_string(self, query: str, tokens: list[str], strategy: str = "append") -> str:
        """Expand a query string with synonyms.

        Args:
            query: Original query string
            tokens: Tokenized query
            strategy: Expansion strategy - "append" or "replace"
                - append: Add synonyms to the end (original + synonyms)
                - replace: Replace tokens with "token OR synonym1 OR synonym2"

        Returns:
            Expanded query string
        """
        if strategy == "append":
            expanded_tokens = self.expand_query(tokens, max_expansions=2)
            return " ".join(expanded_tokens)

        elif strategy == "replace":
            expanded_parts = []
            for token in tokens:
                synonyms = self.get_synonyms(token)
                if synonyms:
                    # Create OR clause: (token OR syn1 OR syn2)
                    or_clause = " OR ".join([token] + list(synonyms)[:2])
                    expanded_parts.append(f"({or_clause})")
                else:
                    expanded_parts.append(token)

            return " ".join(expanded_parts)

        else:
            logger.warning(f"Unknown expansion strategy: {strategy}")
            return query

    def save_synonyms(self, file_path: str):
        """Save current synonyms to a JSON file.

        Args:
            file_path: Path to save the synonym dictionary
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Convert sets to lists for JSON serialization
            data = {k: list(v) for k, v in self.synonyms.items()}

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved {len(self.synonyms)} synonym groups to {file_path}")

        except Exception as e:
            logger.error(f"Failed to save synonyms to {file_path}: {e}")


# Global expander instance
_expander: SynonymExpander | None = None


def get_expander(synonym_dict_path: str | None = None) -> SynonymExpander:
    """Get or create the global synonym expander instance.

    Args:
        synonym_dict_path: Path to synonym dictionary (only used on first call)

    Returns:
        SynonymExpander instance
    """
    global _expander
    if _expander is None:
        _expander = SynonymExpander(synonym_dict_path)
    return _expander
