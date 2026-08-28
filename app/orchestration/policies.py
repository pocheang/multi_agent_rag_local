"""Pure policies that decide which optional orchestration stages are allowed."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts import RouteDecision, TaskPlan
from app.pipeline.profiles import PipelineProfile


class UnsupportedRouteError(ValueError):
    """Raised when a router emits a route outside the profile contract."""


@dataclass(frozen=True)
class ExecutionPolicy:
    """One policy object selects profile behavior on the shared Engine."""

    profile: PipelineProfile = PipelineProfile.ADVANCED
    enable_route_validation: bool = True
    enable_retrieval_quality: bool = False
    require_answer_validation: bool = False
    require_quality_report: bool = False
    allow_planning: bool = True
    allowed_routes: frozenset[str] = frozenset({"vector", "graph", "web", "react", "hybrid", "clarification"})

    @classmethod
    def for_profile(cls, profile: PipelineProfile | str) -> ExecutionPolicy:
        selected = PipelineProfile(profile)
        return cls(
            profile=selected,
            enable_retrieval_quality=True,
            require_answer_validation=True,
            require_quality_report=True,
            allow_planning=True,
        )

    def validate_route(self, route: RouteDecision) -> None:
        actual = route.effective_route
        if actual not in self.allowed_routes:
            raise UnsupportedRouteError(f"unsupported route {actual!r} for {self.profile.value}")

    def should_plan(self, route: RouteDecision) -> bool:
        """Planner execution is allowed only when the router requires it."""
        return self.allow_planning and route.requires_plan

    def should_run_tools(self, route: RouteDecision, plan: TaskPlan | None) -> bool:
        """Run tools only for an explicitly tool-enabled route and plan."""
        return plan is not None and plan.requires_tools and "tool" in route.allowed_capabilities
