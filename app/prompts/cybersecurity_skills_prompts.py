"""Compatibility exports for cybersecurity skill prompts."""

from .skills.cybersecurity_skills_prompts import (
    CYBER_ATTACK_ANALYSIS_SYSTEM_PROMPT,
    CYBER_ATTACK_ANALYSIS_USER_PROMPT_TEMPLATE,
    CYBER_DEFENSE_HARDENING_SYSTEM_PROMPT,
    CYBER_DEFENSE_HARDENING_USER_PROMPT_TEMPLATE,
    INCIDENT_RESPONSE_PLAYBOOK_SYSTEM_PROMPT,
    INCIDENT_RESPONSE_PLAYBOOK_USER_PROMPT_TEMPLATE,
    get_cyber_attack_analysis_prompts,
    get_cyber_defense_hardening_prompts,
    get_incident_response_playbook_prompts,
)

__all__ = [
    "CYBER_ATTACK_ANALYSIS_SYSTEM_PROMPT",
    "CYBER_ATTACK_ANALYSIS_USER_PROMPT_TEMPLATE",
    "CYBER_DEFENSE_HARDENING_SYSTEM_PROMPT",
    "CYBER_DEFENSE_HARDENING_USER_PROMPT_TEMPLATE",
    "INCIDENT_RESPONSE_PLAYBOOK_SYSTEM_PROMPT",
    "INCIDENT_RESPONSE_PLAYBOOK_USER_PROMPT_TEMPLATE",
    "get_cyber_attack_analysis_prompts",
    "get_cyber_defense_hardening_prompts",
    "get_incident_response_playbook_prompts",
]
