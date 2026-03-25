# agentops-cloud-platform

Cloud-oriented multi-agent workflow platform designed to feel like a serious systems/product project, not a toy chatbot demo. Users assemble role-based AI agents, orchestrate async workflows, persist shared state, gate final deliverables behind approvals, and keep a durable audit trail for operational clarity.

## Why this project exists

In real agentic systems, the “agent” is only one part of the product. Teams need:

- deterministic orchestration and state transitions
- persistence (run history, artifacts, approvals)
- operational audit logs (who/what/when)
- provider-agnostic LLM integration
- a clean UX that makes workflow progress understandable

This project focuses on that platform layer.

## Key Features

- Built-in default agent templates (Coordinator, Research Analyst, Writer, Reviewer)
- User-defined custom agents persisted per workspace
- Async workflow orchestration via Celery + Redis
- A real workflow state machine (planning -> running -> awaiting approval -> completed/failed)
- Shared per-run context persisted in Postgres
- Artifact storage for every agent output
- Approval checkpoints before final deliverables
- Persistent activity log for an audit trail
- Provider abstraction (mock provider for demo; OpenAI provider stub for later)

## Architecture Overview

### Backend (FastAPI)

Backend structure:

- `app/api/v1/router.py`: REST routes (workspaces, agents, templates, workflows, runs, approvals, activity logs)
- `app/models/`: SQLAlchemy relational model + enums
- `app/schemas/`: Pydantic request/response models
- `app/services/`: service layer (LLM abstraction, prompt builder, workflow orchestrator, agent execution, approval gating via state machine)
- `app/workflows/`: workflow state machine transitions
- `app/tasks/`: Celery worker entrypoints for async execution
- `app/db/`: database session + create_all init

LLM logic is encapsulated behind `app/services/llm.py` with a `MockLLMProvider` default and an optional `OpenAILLMProvider` stub.

### Workflow Engine

Workflow runs progress through explicit states stored in `workflow_runs.status`:

- `planning`: coordinator plan is executing
- `running`: agent tasks are executing in order
- `awaiting_approval`: reviewer checkpoint is pending human decision
- `completed`: final deliverable produced
- `failed`: execution halted due to rejection/errors

Transitions are handled by `app/workflows/state_machine.py`.

### Async Execution

Celery schedules one job per assignment:

- `execute_agent_task(assignment_id, user_id)`

After the agent writes its artifact + marks completion, the workflow state machine decides the next scheduling point.

## Database Model Summary

Tables:

- `users`
- `workspaces`
- `agent_templates` (seeded defaults)
- `agents` (workspace-scoped, including custom agents)
- `workflows` and `workflow_participants`
- `workflow_runs`
- `tasks`
- `task_assignments`
- `handoffs`
- `artifacts`
- `approvals`
- `activity_logs`

Artifacts and approvals are first-class objects (not ephemeral logs), enabling a persistent run history.

## Local Setup

1. Create your `.env`:

```bash
cp .env.example .env
```

2. Start the full stack:

```bash
docker compose up --build
```

3. Open the UI:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000/api/v1`

The system seeds demo templates, a demo workspace, and one demo workflow run (awaiting approval) on first startup.

## Seeded Demo Workflow (In-App)

On first startup, the backend seeds a complete demo scenario in the project data model:

- Workspace: `Demo Workspace`
- Workflow: `AgentOps Demo`
- Seeded run state: `awaiting_approval`
- Includes tasks, assignments, artifacts, activity logs, and one pending approval checkpoint

In the app:

1. Open `http://localhost:3000/dashboard`.
2. Open `Demo Workspace`.
3. Click `Open Demo Run` in the "Demo Workflow Ready" panel.
4. Inspect generated artifacts and activity logs.
5. Submit an approval decision to complete or reject the run.

This gives a fast end-to-end walkthrough without creating data manually.

## Demo Authentication

For local/demo purposes the API uses a simple bearer token (`API_AUTH_TOKEN` in `.env`) plus an `x-user-id` header.
The frontend container injects these headers automatically via `NEXT_PUBLIC_API_AUTH_TOKEN` and `NEXT_PUBLIC_USER_ID`.

## Demo Workflow Lifecycle (High Level)

1. Create workflow in the UI by selecting participating agents and a goal.
2. Start a workflow run:
   - Coordinator produces a step plan.
3. Orchestrator schedules tasks in order:
   - Research -> Draft -> Review -> Finalize
4. Reviewer triggers a human approval checkpoint before final deliverables.
5. Approve in the run detail screen:
   - Finalize executes and the final artifact is persisted.

## Future Improvements

- Add workspace-level run listing filters (status, time range)
- Implement richer retry/idempotency semantics for Celery tasks
- Add real structured output validation (Pydantic/JSON schema) per agent type
- Improve handoff visualization in the UI (render `handoffs` directly)
- Add auth beyond demo bearer token (JWT/session) for real multi-user deployment

