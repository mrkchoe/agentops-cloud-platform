import type { ActivityLog } from "@/lib/api";

type CardVariant = "started" | "approval" | "artifact" | "completed" | "failed" | "generic";

function variantFromEvent(eventType: string): CardVariant {
  if (eventType === "workflow_run_created" || eventType.includes("workflow_run_created")) return "started";
  if (eventType === "workflow_plan_created") return "started";
  if (eventType.includes("approval") || eventType === "approval_requested") return "approval";
  if (eventType === "task_completed" || eventType.includes("artifact")) return "artifact";
  if (eventType === "workflow_completed") return "completed";
  if (eventType === "workflow_failed" || eventType.includes("failed")) return "failed";
  return "generic";
}

const titles: Record<CardVariant, string> = {
  started: "Workflow started",
  approval: "Approval requested",
  artifact: "Artifact created",
  completed: "Workflow completed",
  failed: "Workflow failed",
  generic: "Workflow update",
};

const borders: Record<CardVariant, string> = {
  started: "border-brand-200 bg-brand-50/80",
  approval: "border-orange-200 bg-orange-50/90",
  artifact: "border-indigo-200 bg-indigo-50/80",
  completed: "border-emerald-200 bg-emerald-50/80",
  failed: "border-red-200 bg-red-50/80",
  generic: "border-gray-200 bg-white",
};

export function WorkflowEventCard({ log }: { log: ActivityLog }) {
  const v = variantFromEvent(log.event_type);
  return (
    <div className={`mx-auto max-w-lg rounded-lg border px-3 py-2 shadow-sm ${borders[v]}`}>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-600">{titles[v]}</div>
      <div className="mt-1 text-sm text-gray-900">{log.message}</div>
      <div className="mt-1 text-xs text-gray-500">{new Date(log.created_at).toLocaleString()}</div>
    </div>
  );
}
