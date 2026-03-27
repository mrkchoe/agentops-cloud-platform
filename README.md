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
- **Messaging layer**: conversations, messages, and WhatsApp channel bindings (Twilio or Meta) with normalized inbound payloads and outbound delivery
- **Inbox UI**: workspace-scoped inbox with conversation list, thread, composer, workflow event cards, and polling for updates

## Architecture Overview

### Backend (FastAPI)

Backend structure:

- `app/api/v1/router.py`: REST routes (workspaces, agents, templates, workflows, runs, approvals, activity logs)
- `app/api/v1/messaging_routes.py`: conversations, messages, WhatsApp webhooks (inbound, Meta verify, status)
- `app/models/`: SQLAlchemy relational model + enums
- `app/schemas/`: Pydantic request/response models
- `app/services/`: service layer (LLM abstraction, prompt builder, workflow orchestrator, agent execution, approval gating via state machine)
- `app/services/channels/`: channel adapters (`twilio_whatsapp`, `meta_whatsapp`, shared types and `get_whatsapp_adapter()`)
- `app/services/conversation_service.py`, `messaging_service.py`, `messaging_inbound.py`, `messaging_workflow_hooks.py`: conversation CRUD, inbound processing, workflow-linked notifications
- `app/workflows/`: workflow state machine transitions
- `app/tasks/`: Celery worker entrypoints (agent execution, WhatsApp inbound processing, conversation notifications, web→WhatsApp mirroring)
- `app/db/`: database session + additive `create_all` on startup

LLM logic is encapsulated behind `app/services/llm.py` with a `MockLLMProvider` default and an optional `OpenAILLMProvider` stub. Conversational turns for the messaging layer use `generate_conversational()` on the same provider abstraction.

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
- `conversations`, `conversation_participants`, `messages`, `channel_bindings`, `status_callback_dedupe`

Artifacts and approvals are first-class objects (not ephemeral logs), enabling a persistent run history.

## Messaging and WhatsApp

The platform treats messaging as a first-class domain alongside workflows:

- **Conversations** are scoped to a workspace and can link to a **workflow run** (`linked_workflow_run_id`).
- **Channel bindings** tie an external address (e.g. WhatsApp E.164) to a conversation and optional default agent; inbound webhooks resolve or create the binding and conversation.
- **Providers**: set `WHATSAPP_PROVIDER=twilio` or `meta`. Adapters implement inbound parsing, outbound text send, optional signature verification (`WHATSAPP_VERIFY_SIGNATURE`), and status callbacks.
- **Webhooks** (public, signature-checked when enabled):
  - `POST /api/v1/channels/whatsapp/inbound` — inbound messages (uses `DEFAULT_WHATSAPP_WORKSPACE_ID` when the webhook cannot infer a workspace).
  - `GET /api/v1/channels/whatsapp/webhook/verify` — Meta subscription challenge (`hub.verify_token` vs `WHATSAPP_WEBHOOK_VERIFY_TOKEN` or `META_VERIFY_TOKEN`).
  - `POST /api/v1/channels/whatsapp/status` — delivery status updates (deduped).
- **Celery**: inbound messages enqueue `process_whatsapp_inbound_message` (LLM reply and optional workflow escalation). Workflow progress can notify linked conversations via `send_conversation_notification`. Web UI replies in a WhatsApp-bound conversation enqueue `deliver_web_reply_to_whatsapp` to mirror text to WhatsApp.
- **SQL reference**: `backend/migrations/001_messaging_domain.sql` documents Postgres-oriented DDL; local dev typically relies on SQLAlchemy `create_all` for missing tables.

### Messaging-related environment variables

| Variable | Purpose |
|----------|---------|
| `WHATSAPP_PROVIDER` | `twilio` or `meta` |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Meta challenge verification (with `META_VERIFY_TOKEN` as alternate) |
| `WHATSAPP_VERIFY_SIGNATURE` | `true` to validate Twilio / Meta signatures (requires real secrets) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp send + webhook validation |
| `META_WHATSAPP_ACCESS_TOKEN`, `META_WHATSAPP_PHONE_NUMBER_ID`, `META_APP_SECRET`, `META_VERIFY_TOKEN` | Meta Cloud API |
| `DEFAULT_WHATSAPP_WORKSPACE_ID`, `DEFAULT_WHATSAPP_AGENT_ID` | Default workspace for inbound webhooks and optional default agent |

See `.env.example` for copy-paste placeholders.

## Inbox (frontend)

- **Navigation**: header links **Dashboard** and **Inbox**; `/inbox` redirects to the first workspace’s inbox (`/workspaces/{id}/inbox`).
- **Layout**: left sidebar lists conversations; main area shows the thread, a header (channel badge, bound agent, linked run + status), and a bottom composer.
- **Data**: uses `GET/POST /api/v1/conversations` and messages endpoints; polls messages and (when linked) workflow run detail for activity cards.
- **Cards**: workflow events (started, plan, approval, task/artifact, completed/failed) render as inline cards merged into the timeline by activity log type and structured system messages.

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

1. Open `http://localhost:3000/dashboard` or go to **Inbox** for conversations.
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

## Tests

Backend messaging tests live under `backend/tests/` (pytest). From the repo root:

```bash
cd backend && pip install -r requirements.txt && python -m pytest tests/ -v
```

Coverage includes Twilio/Meta inbound parsing helpers, channel binding/conversation creation, and outbound behavior when credentials are absent.

## Future Improvements

- Add workspace-level run listing filters (status, time range)
- Implement richer retry/idempotency semantics for Celery tasks
- Add real structured output validation (Pydantic/JSON schema) per agent type
- Improve handoff visualization in the UI (render `handoffs` directly)
- Add auth beyond demo bearer token (JWT/session) for real multi-user deployment
- Alembic migrations for production schema evolution (today: additive `create_all` + optional SQL in `backend/migrations/`)

