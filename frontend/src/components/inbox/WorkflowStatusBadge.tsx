import type { WorkflowRun } from "@/lib/api";

const statusStyles: Record<string, string> = {
  planning: "bg-amber-100 text-amber-900",
  running: "bg-brand-100 text-brand-900",
  awaiting_approval: "bg-orange-100 text-orange-900",
  completed: "bg-emerald-100 text-emerald-900",
  failed: "bg-red-100 text-red-900",
};

export function WorkflowStatusBadge({ run }: { run: WorkflowRun }) {
  const cls = statusStyles[run.status] ?? "bg-gray-100 text-gray-800";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {run.status.replaceAll("_", " ")}
    </span>
  );
}
