"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  getConversation,
  getWorkflowRunDetail,
  listConversationMessages,
  listConversations,
  postConversationMessage,
  type Conversation,
  type ConversationDetail,
  type ConversationMessage,
  type WorkflowRunDetail,
} from "@/lib/api";
import { ChannelBadge } from "@/components/inbox/ChannelBadge";
import { ConversationList } from "@/components/inbox/ConversationList";
import { MessageComposer } from "@/components/inbox/MessageComposer";
import { MessageThread } from "@/components/inbox/MessageThread";
import { WorkflowStatusBadge } from "@/components/inbox/WorkflowStatusBadge";

export default function WorkspaceInboxPage({ params }: { params: { workspaceId: string } }) {
  const workspaceId = Number(params.workspaceId);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [runDetail, setRunDetail] = useState<WorkflowRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshConversations = useCallback(async () => {
    const list = await listConversations(workspaceId);
    setConversations(list);
    return list;
  }, [workspaceId]);

  const refreshThread = useCallback(
    async (conversationId: number) => {
      const [d, msgs] = await Promise.all([
        getConversation(conversationId),
        listConversationMessages(conversationId),
      ]);
      setDetail(d);
      setMessages(msgs);
      if (d.linked_workflow_run_id) {
        const rd = await getWorkflowRunDetail(d.linked_workflow_run_id);
        setRunDetail(rd);
      } else {
        setRunDetail(null);
      }
    },
    []
  );

  useEffect(() => {
    let cancelled = false;
    setError(null);
    (async () => {
      try {
        const list = await refreshConversations();
        if (cancelled) return;
        setSelectedId((prev) => (prev === null && list[0] ? list[0].id : prev));
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshConversations]);

  useEffect(() => {
    if (selectedId === null) return;
    let cancelled = false;
    setError(null);
    (async () => {
      try {
        await refreshThread(selectedId);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId, refreshThread]);

  useEffect(() => {
    if (selectedId === null) return;
    const poll = setInterval(() => {
      void refreshThread(selectedId).catch(() => {});
    }, 4000);
    return () => clearInterval(poll);
  }, [selectedId, refreshThread]);

  useEffect(() => {
    const poll = setInterval(() => {
      void refreshConversations().catch(() => {});
    }, 5000);
    return () => clearInterval(poll);
  }, [refreshConversations]);

  async function onSend(text: string) {
    if (selectedId === null) return;
    await postConversationMessage(selectedId, { body_text: text });
    await refreshThread(selectedId);
    await refreshConversations();
  }

  const channel = detail?.primary_channel === "whatsapp" ? "whatsapp" : "web";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xl font-semibold">Inbox</div>
          <div className="text-sm text-gray-600">Conversations across web and WhatsApp.</div>
        </div>
        <Link
          href={`/workspaces/${workspaceId}`}
          className="rounded-md border bg-white px-3 py-2 text-sm hover:bg-gray-50"
        >
          ← Workspace
        </Link>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="flex h-[min(720px,calc(100vh-11rem))] min-h-[420px] flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm lg:flex-row">
        <aside className="flex max-h-[40vh] flex-col border-b border-gray-200 lg:max-h-none lg:w-80 lg:border-b-0 lg:border-r">
          <div className="border-b border-gray-100 px-3 py-2 text-sm font-semibold text-gray-800">Conversations</div>
          <ConversationList
            conversations={conversations}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId(id)}
          />
        </aside>

        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          {selectedId === null ? (
            <div className="flex flex-1 items-center justify-center text-sm text-gray-500">
              Select a conversation or wait for new messages.
            </div>
          ) : !detail ? (
            <div className="flex flex-1 items-center justify-center text-sm text-gray-500">Loading conversation…</div>
          ) : (
            <>
              <header className="border-b border-gray-100 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-gray-900">{detail.title || `Conversation #${detail.id}`}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-600">
                      <ChannelBadge channel={channel} />
                      {detail.binding_agent_name && (
                        <span>
                          Agent: <span className="font-medium text-gray-800">{detail.binding_agent_name}</span>
                        </span>
                      )}
                      {detail.linked_workflow_run_id && detail.workflow_run && (
                        <span className="flex items-center gap-2">
                          <Link
                            href={`/workspaces/${workspaceId}/workflows/${detail.workflow_run.workflow_id}/runs/${detail.linked_workflow_run_id}`}
                            className="text-brand-700 hover:underline"
                          >
                            Run #{detail.linked_workflow_run_id}
                          </Link>
                          <WorkflowStatusBadge run={detail.workflow_run} />
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </header>

              <MessageThread
                messages={messages}
                activityLogs={runDetail?.activity_logs ?? []}
                workflowRun={detail.workflow_run}
              />

              <MessageComposer disabled={false} onSend={onSend} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}
