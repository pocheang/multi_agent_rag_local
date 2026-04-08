from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    description: str
    instruction: str


SKILLS = {
    "answer_with_citations": Skill(
        name="answer_with_citations",
        description="基于检索证据回答，并强制引用来源。",
        instruction=(
            "你必须严格基于提供的上下文回答。若上下文不足，要明确说明不确定。"
            "输出时优先引用来源标签。"
        ),
    ),
    "compare_entities": Skill(
        name="compare_entities",
        description="比较两个或多个实体的异同点。",
        instruction="从能力、关系、作用、证据来源几个维度进行比较。",
    ),
    "timeline_builder": Skill(
        name="timeline_builder",
        description="从上下文中抽取事件时间线。",
        instruction="按时间顺序组织事实；无法确认时间时要标注约束。",
    ),
    "web_fact_check": Skill(
        name="web_fact_check",
        description="当本地知识不足时，使用联网结果补充事实并明确区分来源。",
        instruction="将联网结果与本地知识分开陈述，优先本地知识，网络只做补充和校验。",
    ),
    "cyber_attack_analysis": Skill(
        name="cyber_attack_analysis",
        description="面向网络安全场景分析攻击方法、攻击链路与风险影响。",
        instruction=(
            "按 ATT&CK/攻击链视角描述：攻击目标、前置条件、常见手法、可观测痕迹。"
            "可以解释原理，但不要提供可直接滥用的逐步攻击操作。"
        ),
    ),
    "cyber_defense_hardening": Skill(
        name="cyber_defense_hardening",
        description="给出防护、检测、加固与基线配置建议。",
        instruction=(
            "按优先级输出：立即止血、短期加固、长期治理。"
            "覆盖身份、主机、网络、应用、数据与监控告警。"
        ),
    ),
    "incident_response_playbook": Skill(
        name="incident_response_playbook",
        description="输出可执行的应急响应流程和处置清单。",
        instruction=(
            "按阶段输出：识别、遏制、根除、恢复、复盘。"
            "每阶段给关键动作、证据保全点、沟通与升级建议。"
        ),
    ),
    "ai_knowledge_assistant": Skill(
        name="ai_knowledge_assistant",
        description="面向人工智能主题的问答、概念解释、方案比较与工程建议。",
        instruction=(
            "优先给出清晰概念定义、适用场景、优缺点和落地建议。"
            "涉及模型评估或选型时，说明假设条件与边界。"
        ),
    ),
    "pdf_text_reader": Skill(
        name="pdf_text_reader",
        description="面向 PDF 文本读取与提炼，输出结构化信息摘要。",
        instruction=(
            "优先从提供的 PDF 相关上下文中提取关键段落、要点和结论。"
            "对无法确认的页码或字段要明确标注不确定。"
        ),
    ),
}


def get_skill(name: str) -> Skill:
    return SKILLS.get(name, SKILLS["answer_with_citations"])
