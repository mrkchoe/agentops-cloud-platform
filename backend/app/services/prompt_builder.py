from typing import Any

from app.models.entities import Agent, TaskKind


def _pretty_context(shared_context: dict[str, Any]) -> str:
    # Keep it readable for both the mock provider and real providers.
    if not shared_context:
        return "No shared context yet."
    lines = ["Shared Context:"]
    for k, v in shared_context.items():
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            lines.append(f"- {k}: {str(v)[:800]}")  # avoid enormous prompts
        else:
            lines.append(f"- {k}: {str(v)[:800]}")
    return "\n".join(lines)


class PromptBuilder:
    def build_messages(
        self,
        *,
        agent: Agent,
        task_kind: TaskKind,
        objective: str,
        workflow_goal: str,
        shared_context: dict[str, Any],
        prior_artifacts: list[str],
    ) -> tuple[list[dict[str, str]], str | None]:
        system = (
            f"You are {agent.name} ({agent.role_title}).\n"
            f"Description: {agent.description}\n"
            f"System instructions:\n{agent.system_instructions}\n"
            f"Output format hint:\n{agent.output_format_hint}\n"
        )

        prior_blob = "\n\n".join([f"Artifact {i+1}:\n{t}" for i, t in enumerate(prior_artifacts)]) if prior_artifacts else ""

        # The response_hint is used by providers that can respond in structured formats.
        response_hint: str | None = "json" if task_kind in (TaskKind.PLAN, TaskKind.RESEARCH, TaskKind.REVIEW) else None

        user = "\n".join(
            [
                f"Goal: {workflow_goal}",
                f"Task Kind: {task_kind.value}",
                f"Objective: {objective}",
                _pretty_context(shared_context),
                f"Prior artifacts:\n{prior_blob if prior_blob else 'None'}",
            ]
        )

        if "revision_notes" in shared_context:
            user += f"\nRevision Notes: {shared_context.get('revision_notes')}"

        return [{"role": "system", "content": system}, {"role": "user", "content": user}], response_hint

