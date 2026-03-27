import asyncio
from datetime import datetime

from app.db.session import db_session
from app.models.entities import (
    AssignmentStatus,
    Task,
    TaskAssignment,
    TaskStatus,
    WorkflowStatus,
    WorkflowRun,
)
from app.services.activity_log import log_event
from app.models.entities import (
    ChannelBinding,
    ChannelKind,
    Conversation,
    DeliveryStatus,
    Message,
    MessageChannel,
    MessageDirection,
    MessageSenderType,
    Workspace,
)
from app.services.agent_execution import AgentExecutionService
from app.services.channels import SendContext
from app.services.messaging_inbound import process_inbound_whatsapp_message
from app.services.messaging_service import deliver_outbound_whatsapp, record_outbound_message
from app.workflows.state_machine import WorkflowStateMachine

from .celery_app import celery_app


@celery_app.task(name="app.tasks.execute_agent_task")
def execute_agent_task(assignment_id: int, user_id: int) -> None:
    """
    Celery entrypoint for executing a single agent assignment.
    After task completion, the workflow state machine schedules the next step.
    """

    with db_session() as db:
        assignment = db.query(TaskAssignment).filter(TaskAssignment.id == assignment_id).one()
        task = db.query(Task).filter(Task.id == assignment.task_id).one()
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task.workflow_run_id).one()

        try:
            AgentExecutionService().execute_assignment(db=db, assignment_id=assignment_id, user_id=user_id)

            next_assignment_id = WorkflowStateMachine().on_task_completed(
                db=db,
                workflow_run_id=run.id,
                assignment_id=assignment_id,
                user_id=user_id,
            )

            if next_assignment_id is not None:
                execute_agent_task.delay(next_assignment_id, user_id)
        except Exception as e:
            now = datetime.utcnow()
            assignment.status = AssignmentStatus.FAILED
            assignment.error = str(e)[:4000]
            assignment.completed_at = now

            task.status = TaskStatus.FAILED
            task.error = str(e)[:8000]
            task.completed_at = now

            run.status = WorkflowStatus.FAILED
            run.error = str(e)[:8000]
            run.completed_at = now

            log_event(
                db,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                user_id=user_id,
                event_type="workflow_failed",
                message="Workflow task execution failed.",
                metadata={"assignment_id": assignment_id, "task_id": task.id},
            )

            db.add(assignment)
            db.add(task)
            db.add(run)
            db.commit()
            raise


@celery_app.task(name="app.tasks.process_whatsapp_inbound_message")
def process_whatsapp_inbound_message_task(inbound_message_id: int) -> None:
    with db_session() as db:
        process_inbound_whatsapp_message(db, inbound_message_id)


@celery_app.task(name="app.tasks.send_conversation_notification")
def send_conversation_notification_task(
    conversation_id: int,
    message: str,
    body_structured: dict,
    event_type: str,
) -> None:
    """Push workflow progress / approval checkpoints to WhatsApp when a run is linked to a conversation."""
    with db_session() as db:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).one()
        binding = (
            db.query(ChannelBinding)
            .filter(ChannelBinding.conversation_id == conversation_id, ChannelBinding.channel == ChannelKind.WHATSAPP)
            .first()
        )
        if not binding:
            binding = db.query(ChannelBinding).filter(ChannelBinding.conversation_id == conversation_id).first()
        if not binding:
            return

        to_addr = binding.external_user_address
        ctx = SendContext(workspace_id=conv.workspace_id, conversation_id=conv.id, metadata={"event": event_type})
        ok, prov_id, err = asyncio.run(
            deliver_outbound_whatsapp(to_address=to_addr, body=message, context=ctx)
        )

        structured = dict(body_structured or {})
        structured.setdefault("event_type", event_type)

        msg = Message(
            conversation_id=conv.id,
            sender_type=MessageSenderType.SYSTEM,
            body_text=message,
            body_structured=structured,
            direction=MessageDirection.OUTBOUND,
            channel=MessageChannel.WHATSAPP,
            provider=binding.provider,
            provider_message_id=prov_id,
            reply_to_message_id=None,
            delivery_status=DeliveryStatus.SENT if ok else DeliveryStatus.FAILED,
        )
        db.add(msg)

        ws = db.query(Workspace).filter(Workspace.id == conv.workspace_id).one()
        log_event(
            db,
            workspace_id=conv.workspace_id,
            workflow_run_id=structured.get("workflow_run_id"),
            user_id=ws.user_id,
            event_type=f"whatsapp_{event_type}",
            message=message[:500],
            metadata={"conversation_id": conversation_id, "provider_message_id": prov_id, "error": err},
        )
        db.commit()


@celery_app.task(name="app.tasks.deliver_web_reply_to_whatsapp")
def deliver_web_reply_to_whatsapp_task(conversation_id: int, source_message_id: int) -> None:
    """Mirror a web composer message to WhatsApp when a WhatsApp channel binding exists."""
    with db_session() as db:
        binding = (
            db.query(ChannelBinding)
            .filter(
                ChannelBinding.conversation_id == conversation_id,
                ChannelBinding.channel == ChannelKind.WHATSAPP,
            )
            .first()
        )
        if not binding:
            return

        web_msg = db.query(Message).filter(Message.id == source_message_id).one()
        if web_msg.channel != MessageChannel.WEB or web_msg.direction != MessageDirection.INBOUND:
            return

        conv = db.query(Conversation).filter(Conversation.id == conversation_id).one()
        ctx = SendContext(
            workspace_id=conv.workspace_id,
            conversation_id=conv.id,
            reply_to_provider_message_id=None,
            metadata={"source": "web_composer", "web_message_id": source_message_id},
        )
        ok, prov_id, err = asyncio.run(
            deliver_outbound_whatsapp(
                to_address=binding.external_user_address,
                body=web_msg.body_text,
                context=ctx,
            )
        )

        record_outbound_message(
            db,
            conversation_id=conv.id,
            agent_id=binding.agent_id,
            body_text=web_msg.body_text,
            body_structured={"mirrored_from_web_message_id": source_message_id},
            provider=binding.provider,
            reply_to_message_id=source_message_id,
            provider_message_id=prov_id,
            delivery_status=DeliveryStatus.SENT if ok else DeliveryStatus.FAILED,
            sender_type=MessageSenderType.USER,
            sender_id=web_msg.sender_id,
        )

        binding.last_outbound_at = datetime.utcnow()
        db.add(binding)
        conv.updated_at = datetime.utcnow()
        db.add(conv)

        ws = db.query(Workspace).filter(Workspace.id == conv.workspace_id).one()
        log_event(
            db,
            workspace_id=conv.workspace_id,
            workflow_run_id=conv.linked_workflow_run_id,
            user_id=ws.user_id,
            event_type="whatsapp_outbound_from_web",
            message=web_msg.body_text[:500],
            metadata={"conversation_id": conversation_id, "provider_message_id": prov_id, "error": err},
        )
        db.commit()

