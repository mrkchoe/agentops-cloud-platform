import json
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.entities import Agent, TaskKind


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str | None = None


class AgentLLMProvider:
    def generate(self, *, agent: Agent, task_kind: TaskKind, messages: list[dict[str, str]], response_hint: str | None) -> LLMResult:
        raise NotImplementedError

    def generate_conversational(
        self,
        *,
        agent: Agent,
        messages: list[dict[str, str]],
        response_hint: str | None = "json",
    ) -> LLMResult:
        """Short conversational turn (chat / WhatsApp). Default JSON with reply + optional workflow escalation."""
        raise NotImplementedError


class MockLLMProvider(AgentLLMProvider):
    """
    Deterministic, no-external-call provider for local demos.
    It returns JSON for coordinator/reviewer and markdown/text for writers.
    """

    def generate(self, *, agent: Agent, task_kind: TaskKind, messages: list[dict[str, str]], response_hint: str | None) -> LLMResult:
        # Extract a simple goal hint from the user message to make outputs feel contextual.
        user_text = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        goal_line = ""
        for line in user_text.splitlines():
            if line.lower().startswith("goal:"):
                goal_line = line.split(":", 1)[1].strip()
                break
        goal_line = goal_line or "the specified business goal"

        role = (agent.role_title or "").lower()

        if task_kind == TaskKind.PLAN and "coordinator" in role:
            steps = [
                {"kind": TaskKind.RESEARCH.value, "objective": f"Collect context for: {goal_line}"},
                {"kind": TaskKind.DRAFT.value, "objective": f"Draft a deliverable for: {goal_line}"},
                {"kind": TaskKind.REVIEW.value, "objective": f"Review and verify requirements for: {goal_line}"},
                {
                    "kind": TaskKind.FINALIZE.value,
                    "objective": "Produce final output using approved context (include any revision notes).",
                },
            ]
            payload: dict[str, Any] = {
                "steps": steps,
                "notes": "Plan created by mock coordinator.",
            }
            return LLMResult(text=json.dumps(payload, indent=2), model="mock-coordinator")

        if task_kind == TaskKind.REVIEW and "review" in role:
            # If the goal contains "platform" assume it needs minor improvements, else approve.
            needs_revision = "platform" in goal_line.lower()
            payload = {
                "approved": not needs_revision,
                "issues": [
                    "Ensure workflow state transitions and audit trail are explicit.",
                    "Keep prompts centralized and provider-agnostic.",
                ]
                if needs_revision
                else [],
                "revision_notes": "Revise state machine documentation and align artifacts with task kinds.",
            }
            return LLMResult(text=json.dumps(payload, indent=2), model="mock-reviewer")

        if task_kind in (TaskKind.RESEARCH,) and "research" in role:
            payload = {
                "key_points": [
                    "Model the workflow as a state machine with persisted transitions.",
                    "Store every agent output as an artifact for traceability.",
                    "Create approval checkpoints before final deliverables.",
                ],
                "open_questions": ["Which steps should be human-gated vs auto-executed?"],
            }
            return LLMResult(text=json.dumps(payload, indent=2), model="mock-research-analyst")

        if task_kind in (TaskKind.DRAFT, TaskKind.FINALIZE) and "writer" in role:
            # Include brief revision instructions if present in the prompt.
            revision_hint = ""
            for line in user_text.splitlines():
                if line.lower().startswith("revision notes:"):
                    revision_hint = line.split(":", 1)[1].strip()
                    break

            title = "AgentOps Cloud Platform Deliverable"
            body = [
                f"# {title}",
                "",
                f"## Goal",
                f"{goal_line}",
                "",
                "## Draft / Final Output",
                "This deliverable is generated using approved workflow context and role-specific instructions.",
            ]
            if revision_hint:
                body += ["", "## Revision Notes", revision_hint]

            body += [
                "",
                "## Included Mechanisms",
                "- Async workflow orchestration (Celery + Redis)",
                "- Shared persisted state per run",
                "- Role-based multi-agent routing",
                "- Approval checkpoint before final deliverable",
                "- Persistent audit logs for operational seriousness",
            ]

            return LLMResult(text="\n".join(body), model="mock-writer")

        # Generic fallback: return a short text blob.
        return LLMResult(text=f"Mock output for {agent.role_title} / {task_kind}", model="mock-fallback")

    def generate_conversational(
        self,
        *,
        agent: Agent,
        messages: list[dict[str, str]],
        response_hint: str | None = "json",
    ) -> LLMResult:
        user_text = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        wants_workflow = "workflow" in user_text.lower() or "run" in user_text.lower()
        payload = {
            "reply": f"Mock assistant ({agent.name}): {user_text[:400] or 'Hello.'}",
            "start_workflow": wants_workflow,
            "workflow_id": None,
            "reason": "mock conversational routing",
        }
        return LLMResult(text=json.dumps(payload, indent=2), model="mock-conversational")


class OpenAILLMProvider(AgentLLMProvider):
    @retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=6), stop=stop_after_attempt(3))
    def generate(self, *, agent: Agent, task_kind: TaskKind, messages: list[dict[str, str]], response_hint: str | None) -> LLMResult:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        # NOTE: Kept minimal for portfolio purposes; swap to other providers by implementing AgentLLMProvider.
        model = "gpt-4o-mini"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }
        if response_hint:
            payload["response_format"] = {"type": "json_object"}  # best-effort when prompt asks for JSON

        with httpx.Client(timeout=30) as client:
            r = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            return LLMResult(text=text, model=model)

    def generate_conversational(
        self,
        *,
        agent: Agent,
        messages: list[dict[str, str]],
        response_hint: str | None = "json",
    ) -> LLMResult:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        model = "gpt-4o-mini"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
        }
        if response_hint:
            payload["response_format"] = {"type": "json_object"}

        with httpx.Client(timeout=45) as client:
            r = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            return LLMResult(text=text, model=model)


def get_provider() -> AgentLLMProvider:
    if settings.llm_provider.lower() == "openai":
        return OpenAILLMProvider()
    return MockLLMProvider()

