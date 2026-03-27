"use client";

import type { ActivityLog, ConversationMessage, WorkflowRun } from "@/lib/api";
import { WorkflowEventCard } from "./WorkflowEventCard";

const ACTIVITY_CARD_TYPES = new Set([
  "workflow_run_created",
  "workflow_plan_created",
  "approval_requested",
  "task_completed",
  "workflow_completed",
  "workflow_failed",
]);

type TimelineEntry =
  | { kind: "message"; at: string; message: ConversationMessage }
  | { kind: "activity"; at: string; log: ActivityLog };

function buildTimeline(messages: ConversationMessage[], activityLogs: ActivityLog[]): TimelineEntry[] {
  const entries: TimelineEntry[] = [];

  for (const m of messages) {
    const kind = m.body_structured && typeof m.body_structured === "object" ? (m.body_structured as { kind?: string }).kind : undefined;
    if (kind === "approval_checkpoint" && m.sender_type === "system") {
      const synthetic: ActivityLog = {
        id: -m.id,
        workspace_id: 0,
        workflow_run_id: typeof m.body_structured?.workflow_run_id === "number" ? m.body_structured.workflow_run_id : null,
        user_id: 0,
        event_type: "approval_requested",
        message: m.body_text,
        metadata: (m.body_structured as Record<string, unknown>) ?? {},
        created_at: m.created_at,
      };
      entries.push({ kind: "activity", at: m.created_at, log: synthetic });
      continue;
    }
    entries.push({ kind: "message", at: m.created_at, message: m });
  }

  for (const log of activityLogs) {
    if (!ACTIVITY_CARD_TYPES.has(log.event_type)) continue;
    entries.push({ kind: "activity", at: log.created_at, log });
  }

  entries.sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());

  const seen = new Set<string>();
  const deduped: TimelineEntry[] = [];
  for (const e of entries) {
    const key =
      e.kind === "message"
        ? `m-${e.message.id}`
        : `a-${e.log.id}-${e.log.event_type}-${e.log.created_at}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(e);
  }
  return deduped;
}

function Bubble({ message }: { message: ConversationMessage }) {
  const isUserWeb =
    message.sender_type === "user" && message.direction === "inbound" && message.channel === "web";
  const isUserWhatsAppOut =
    message.sender_type === "user" && message.direction === "outbound" && message.channel === "whatsapp";
  const isExternalInbound = message.direction === "inbound" && message.channel === "whatsapp";
  const isOutbound = message.direction === "outbound";

  const align = isUserWeb ? "ml-auto items-end" : "mr-auto items-start";
  const bubble =
    isUserWeb
      ? "bg-brand-600 text-white"
      : isOutbound && message.channel === "whatsapp"
        ? "bg-emerald-50 text-emerald-950 border border-emerald-200"
        : "bg-white text-gray-900 border border-gray-200";

  const label =
    isExternalInbound
      ? "WhatsApp"
      : isUserWhatsAppOut
        ? "You → WhatsApp"
        : message.sender_type === "agent"
          ? "Agent"
          : message.sender_type === "system"
            ? "System"
            : isUserWeb
              ? "You"
              : "Message";

  return (
    <div className={`flex max-w-[85%] flex-col gap-0.5 ${align}`}>
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`rounded-2xl px-3 py-2 text-sm shadow-sm ${bubble}`}>
        <div className="whitespace-pre-wrap break-words">{message.body_text}</div>
        {message.delivery_status && isOutbound && (
          <div className="mt-1 text-[10px] opacity-70">{message.delivery_status}</div>
        )}
      </div>
      <div className="text-[10px] text-gray-400">{new Date(message.created_at).toLocaleTimeString()}</div>
    </div>
  );
}

export function MessageThread({
  messages,
  activityLogs,
  workflowRun,
}: {
  messages: ConversationMessage[];
  activityLogs: ActivityLog[];
  workflowRun: WorkflowRun | null;
}) {
  const timeline = buildTimeline(messages, activityLogs);

  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-3 py-4">
      {workflowRun && (
        <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50/80 px-3 py-2 text-center text-xs text-gray-600">
          Linked workflow run #{workflowRun.id} · Step {workflowRun.current_step_index} ·{" "}
          <span className="font-medium">{workflowRun.status.replaceAll("_", " ")}</span>
        </div>
      )}

      {timeline.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-sm text-gray-500">No messages yet.</div>
      ) : (
        timeline.map((entry, i) =>
          entry.kind === "message" ? (
            <Bubble key={`m-${entry.message.id}-${i}`} message={entry.message} />
          ) : (
            <WorkflowEventCard key={`a-${entry.log.id}-${entry.log.event_type}-${i}`} log={entry.log} />
          )
        )
      )}
    </div>
  );
}
