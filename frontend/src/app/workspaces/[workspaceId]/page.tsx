"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listAgents, listWorkflows, listWorkflowRuns, type Agent, type Workflow, type WorkflowRun } from "@/lib/api";
import type { ReactNode } from "react";

function Pill({ children }: { children: ReactNode }) {
  return <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">{children}</span>;
}

export default function WorkspacePage({ params }: { params: { workspaceId: string } }) {
  const workspaceId = Number(params.workspaceId);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [a, w, r] = await Promise.all([listAgents(workspaceId), listWorkflows(workspaceId), listWorkflowRuns(workspaceId, 10)]);
        if (!cancelled) {
          setAgents(a);
          setWorkflows(w);
          setRuns(r);
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const demoWorkflow = workflows.find((w) => w.name === "AgentOps Demo");
  const demoRun = demoWorkflow ? runs.find((r) => r.workflow_id === demoWorkflow.id) : undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xl font-semibold">Workspace</div>
          <div className="text-sm text-gray-600">Agent selection, workflow definitions, and orchestration runs.</div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Link
            className="rounded-md border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-medium text-brand-900 hover:bg-brand-100"
            href={`/workspaces/${workspaceId}/inbox`}
          >
            Inbox
          </Link>
          <Link className="rounded-md border bg-white px-3 py-2 text-sm hover:bg-gray-50" href={`/workspaces/${workspaceId}/agents`}>
            Manage Agents
          </Link>
          <Link className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700" href={`/workspaces/${workspaceId}/workflows/new`}>
            New Workflow
          </Link>
        </div>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {demoWorkflow && (
        <div className="rounded-lg border border-brand-200 bg-brand-50/60 p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-brand-900">Demo Workflow Ready</div>
              <div className="mt-1 text-sm text-brand-900/90">
                A seeded workflow is available for a quick walkthrough of planning, routing, review, and approval gating.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {demoRun && (
                <Link
                  className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
                  href={`/workspaces/${workspaceId}/workflows/${demoWorkflow.id}/runs/${demoRun.id}`}
                >
                  Open Demo Run
                </Link>
              )}
              <Link
                className="rounded-md border bg-white px-3 py-2 text-sm hover:bg-gray-50"
                href={`/workspaces/${workspaceId}/workflows/new`}
              >
                Clone Demo Idea
              </Link>
            </div>
          </div>
          <div className="mt-2 text-xs text-brand-900/80">
            {demoRun ? `Current demo run status: ${demoRun.status.replaceAll("_", " ")}.` : "Open Workflow Builder to start a new run from this demo workflow."}
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-semibold">Active Agents</div>
            <Pill>{agents.filter((a) => a.is_active).length} active</Pill>
          </div>
          {agents.length === 0 ? (
            <div className="text-sm text-gray-600">No agents yet.</div>
          ) : (
            <div className="space-y-3">
              {agents
                .filter((a) => a.is_active)
                .map((a) => (
                  <div key={a.id} className="rounded-md border bg-gray-50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold">{a.role_title}</div>
                        <div className="text-xs text-gray-600">{a.name}</div>
                      </div>
                      <Pill>{a.approval_required ? "Approval required" : "Auto"}</Pill>
                    </div>
                    <div className="mt-2 text-xs text-gray-700">{a.description}</div>
                  </div>
                ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-semibold">Workflows</div>
            <Pill>{workflows.length} defined</Pill>
          </div>
          {workflows.length === 0 ? (
            <div className="text-sm text-gray-600">No workflows yet. Create one to launch a run.</div>
          ) : (
            <div className="space-y-3">
              {workflows.map((w) => (
                <div key={w.id} className="rounded-md border bg-gray-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold">{w.name}</div>
                      <div className="text-xs text-gray-600">{w.goal}</div>
                    </div>
                    <Pill>{w.require_human_approval ? "Human-gated" : "Auto-finalize"}</Pill>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="mt-3 text-xs text-gray-500">
            Tip: define a new run from the workflow builder.
          </div>
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-semibold">Recent Workflow Runs</div>
            <Pill>{runs.length} runs</Pill>
          </div>
          {runs.length === 0 ? (
            <div className="text-sm text-gray-600">No runs yet. Create a workflow and launch a run.</div>
          ) : (
            <div className="space-y-3">
              {runs.map((run) => (
                <Link key={run.id} href={`/workspaces/${workspaceId}/workflows/${run.workflow_id}/runs/${run.id}`} className="block">
                  <div className="rounded-md border bg-gray-50 p-3 hover:bg-white">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold">Run #{run.id}</div>
                        <div className="text-xs text-gray-600">
                          Created {new Date(run.created_at).toLocaleString()} • Step {run.current_step_index}
                        </div>
                      </div>
                      <Pill>{run.status.replaceAll("_", " ")}</Pill>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

