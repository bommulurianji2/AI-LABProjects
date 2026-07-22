from fastapi import Request

from app.agents_registry.registry import AgentRegistry


def get_registry(request: Request) -> AgentRegistry:
    return request.app.state.registry
