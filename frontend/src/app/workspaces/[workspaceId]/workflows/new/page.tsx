"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createWorkflow,
  listAgents,
  startWorkflowRun,
  type Agent,
} from "@/lib/api";

export default function NewWorkflowPage({ params }: { params: { workspaceId: string } }) {
  const workspaceId = Number(params.workspaceId);
  const router = useRouter();

  const [agents, setAgents] = useState<Agent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [name, setName] = useState("New Multi-Agent Workflow");
  const [goal, setGoal] = useState("");
  const [requireHumanApproval, setRequireHumanApproval] = useState(true);
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const a = await listAgents(workspaceId);
        if (cancelled) return;
        setAgents(a);
        // default: enable the common set if present
        const defaults = ["Coordinator", "Research Analyst", "Writer", "Reviewer"];
        const defaultAgents = a
          .filter((x) => defaults.includes(x.role_title))
          .map((x) => x.id);
        setSelectedAgentIds(defaultAgents);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const activeAgents = useMemo(() => agents.filter((a) => a.is_active), [agents]);

  async function onLaunch() {
    setLoading(true);
    setError(null);
    try {
      if (!goal.trim()) throw new Error("Please provide a goal/task.");
      if (selectedAgentIds.length < 2) throw new Error("Select at least 2 participating agents.");

      const workflow = await createWorkflow(workspaceId, {
        name: name.trim(),
        goal: goal.trim(),
        participant_agent_ids: selectedAgentIds,
        require_human_approval: requireHumanApproval,
      });

      const run = await startWorkflowRun(workflow.id);

      router.push(`/workspaces/${workspaceId}/workflows/${workflow.id}/runs/${run.run_id}`);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="text-xl font-semibold">Workflow Builder</div>
        <div className="text-sm text-gray-600">Define a goal, assemble an agent team, and launch a workflow run.</div>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="space-y-3">
            <input className="w-full rounded-md border bg-white px-3 py-2 text-sm" value={name} onChange={(e) => setName(e.target.value)} />
            <textarea className="w-full rounded-md border bg-white px-3 py-2 text-sm" rows={6} placeholder="What should the team accomplish?" value={goal} onChange={(e) => setGoal(e.target.value)} />
            <label className="flex items-center justify-between gap-3 text-sm">
              <span>Require human approval before final deliverable</span>
              <input type="checkbox" checked={requireHumanApproval} onChange={(e) => setRequireHumanApproval(e.target.checked)} />
            </label>
          </div>
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="mb-2 text-sm font-semibold">Participating Agents</div>

          {activeAgents.length === 0 ? (
            <div className="text-sm text-gray-600">No active agents available.</div>
          ) : (
            <div className="space-y-3">
              {activeAgents.map((a) => {
                const checked = selectedAgentIds.includes(a.id);
                return (
                  <div key={a.id} className="rounded-md border bg-gray-50 p-3">
                    <label className="flex cursor-pointer items-start justify-between gap-3">
                      <span className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            setSelectedAgentIds((prev) =>
                              checked ? prev.filter((id) => id !== a.id) : [...prev, a.id]
                            );
                          }}
                        />
                        <span>
                          <div className="text-sm font-semibold">{a.role_title}</div>
                          <div className="text-xs text-gray-600">{a.name}</div>
                          <div className="mt-1 text-xs text-gray-700">{a.description}</div>
                        </span>
                      </span>
                      <span className="rounded-full border bg-white px-2 py-0.5 text-xs text-gray-700">
                        {a.approval_required ? "Approval required" : "Auto"}
                      </span>
                    </label>
                  </div>
                );
              })}
            </div>
          )}

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={onLaunch}
              disabled={loading}
              className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? "Launching..." : "Create Workflow & Start Run"}
            </button>
          </div>
          <div className="mt-2 text-xs text-gray-500">
            In this portfolio demo, routing decisions use role title keywords and agent configuration hints.
          </div>
        </div>
      </div>
    </div>
  );
}

