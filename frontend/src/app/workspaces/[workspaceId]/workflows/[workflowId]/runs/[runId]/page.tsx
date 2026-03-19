"use client";

import { useEffect, useMemo, useState } from "react";
import { getWorkflowRunDetail, decideApproval, type Artifact, type Approval, type WorkflowRunDetail } from "@/lib/api";

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "completed"
      ? "bg-green-50 text-green-800 border-green-200"
      : status === "failed"
        ? "bg-red-50 text-red-800 border-red-200"
        : status === "awaiting_approval"
          ? "bg-yellow-50 text-yellow-800 border-yellow-200"
          : "bg-blue-50 text-blue-800 border-blue-200";
  return <span className={`rounded-full border px-2 py-0.5 text-xs ${cls}`}>{status.replaceAll("_", " ")}</span>;
}

function ArtifactViewer({ artifact }: { artifact: Artifact }) {
  return (
    <div className="rounded-md border bg-gray-50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-semibold text-gray-700">{artifact.kind}</div>
        <div className="text-[11px] text-gray-500">{new Date(artifact.created_at).toLocaleString()}</div>
      </div>
      <pre className="max-h-[320px] overflow-auto whitespace-pre-wrap break-words text-xs text-gray-900">{artifact.content}</pre>
    </div>
  );
}

export default function WorkflowRunDetailPage({ params }: { params: { workspaceId: string; workflowId: string; runId: string } }) {
  const runId = Number(params.runId);
  const [data, setData] = useState<WorkflowRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [approvalNotes, setApprovalNotes] = useState("");
  const [deciding, setDeciding] = useState(false);

  async function refresh() {
    setError(null);
    const res = await getWorkflowRunDetail(runId);
    setData(res);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await getWorkflowRunDetail(runId);
        if (!cancelled) setData(res);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const pendingApprovals = useMemo(() => {
    return (data?.approvals || []).filter((a) => a.status === "pending");
  }, [data]);

  const finalArtifact = useMemo(() => {
    return (data?.artifacts || []).find((a) => a.kind === "final_deliverable") || null;
  }, [data]);

  async function onDecision(approval: Approval, approved: boolean) {
    setDeciding(true);
    setError(null);
    try {
      await decideApproval(runId, approval.id, { approved, notes: approvalNotes || null });
      setApprovalNotes("");
      // Poll for a short period to reflect Celery progress.
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          await refresh();
          if (i >= 2 && data?.run.status === "completed") break;
        } catch {
          // ignore transient fetch errors during transitions
        }
      }
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setDeciding(false);
    }
  }

  const tasks = (data?.tasks || []).slice().sort((a, b) => a.order_index - b.order_index);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xl font-semibold">Workflow Run</div>
          <div className="text-sm text-gray-600">Status, outputs, approvals, and persistent audit history.</div>
        </div>
        {data && <StatusBadge status={data.run.status} />}
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {loading || !data ? (
        <div className="text-sm text-gray-600">Loading run...</div>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border bg-white p-4 shadow-sm">
              <div className="mb-3 text-sm font-semibold">Task Timeline</div>
              <div className="space-y-3">
                {tasks.map((t) => {
                  const assigned = data.assignments.find((a) => a.task_id === t.id);
                  const agentId = assigned?.agent_id;
                  return (
                    <div key={t.id} className="rounded-md border bg-gray-50 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold">{t.kind}</div>
                          <div className="mt-1 text-xs text-gray-700">{t.objective}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-semibold">{t.status}</div>
                          <div className="text-[11px] text-gray-500">{t.completed_at ? new Date(t.completed_at).toLocaleString() : "In progress"}</div>
                          {agentId ? <div className="text-[11px] text-gray-500 mt-1">Agent ID: {agentId}</div> : null}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg border bg-white p-4 shadow-sm">
                <div className="mb-3 text-sm font-semibold">Approval Checkpoints</div>
                {pendingApprovals.length === 0 ? (
                  <div className="text-sm text-gray-600">No pending approvals.</div>
                ) : (
                  <div className="space-y-3">
                    {pendingApprovals.map((a) => (
                      <div key={a.id} className="rounded-md border bg-gray-50 p-3">
                        <div className="text-sm font-semibold">{a.checkpoint_kind}</div>
                        <div className="mt-1 text-xs text-gray-700">Requested: {new Date(a.requested_at).toLocaleString()}</div>
                        {a.notes ? <div className="mt-2 text-xs text-gray-700">Notes: {a.notes}</div> : null}

                        <div className="mt-3">
                          <div className="text-xs text-gray-600 mb-1">Optional decision notes</div>
                          <textarea
                            className="w-full rounded-md border bg-white px-3 py-2 text-sm"
                            rows={3}
                            value={approvalNotes}
                            onChange={(e) => setApprovalNotes(e.target.value)}
                            placeholder="Add notes for audit trail..."
                          />
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            disabled={deciding}
                            onClick={() => onDecision(a, true)}
                            className="rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            disabled={deciding}
                            onClick={() => onDecision(a, false)}
                            className="rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-lg border bg-white p-4 shadow-sm">
                <div className="mb-3 text-sm font-semibold">Final Deliverable</div>
                {finalArtifact ? (
                  <ArtifactViewer artifact={finalArtifact} />
                ) : (
                  <div className="text-sm text-gray-600">Final output will appear after approval and finalization.</div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-semibold">Agent Outputs (Artifacts)</div>
            <div className="space-y-3">
              {(data.artifacts || [])
                .slice()
                .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
                .map((artifact) => (
                  <ArtifactViewer key={artifact.id} artifact={artifact} />
                ))}
            </div>
          </div>

          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-semibold">Activity Log</div>
            <div className="space-y-3">
              {(data.activity_logs || []).length === 0 ? (
                <div className="text-sm text-gray-600">No log entries.</div>
              ) : (
                (data.activity_logs || []).map((log) => (
                  <div key={log.id} className="rounded-md border bg-gray-50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-xs font-semibold text-gray-700">{log.event_type}</div>
                      <div className="text-[11px] text-gray-500">{new Date(log.created_at).toLocaleString()}</div>
                    </div>
                    <div className="mt-1 text-sm text-gray-900">{log.message}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

