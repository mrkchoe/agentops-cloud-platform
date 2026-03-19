"use client";

import { useEffect, useState } from "react";
import { createCustomAgent, listAgents, setAgentActive, type Agent } from "@/lib/api";

export default function AgentsPage({ params }: { params: { workspaceId: string } }) {
  const workspaceId = Number(params.workspaceId);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    name: "",
    role_title: "",
    description: "",
    system_instructions: "",
    output_format_hint: "Return plain text or structured JSON as appropriate.",
    allowed_handoff_targets_csv: "",
    approval_required: false,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const a = await listAgents(workspaceId);
        if (!cancelled) setAgents(a);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  async function onToggleActive(agent: Agent) {
    setError(null);
    const updated = agents.map((a) => (a.id === agent.id ? { ...a, is_active: !a.is_active } : a));
    setAgents(updated);
    try {
      const res = await setAgentActive(agent.id, { is_active: !agent.is_active });
      setAgents((prev) => prev.map((a) => (a.id === agent.id ? res : a)));
    } catch (e: any) {
      setError(e?.message ?? String(e));
      // Best-effort revert
      setAgents((prev) => prev.map((a) => (a.id === agent.id ? agent : a)));
    }
  }

  async function onCreate() {
    setLoading(true);
    setError(null);
    try {
      const created = await createCustomAgent(workspaceId, {
        name: form.name.trim(),
        role_title: form.role_title.trim(),
        description: form.description.trim(),
        system_instructions: form.system_instructions.trim(),
        output_format_hint: form.output_format_hint.trim(),
        allowed_tools: {},
        allowed_handoff_targets: form.allowed_handoff_targets_csv
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        approval_required: form.approval_required,
        is_active: true,
      } as any);

      setAgents((prev) => [created, ...prev]);
      setForm({
        name: "",
        role_title: "",
        description: "",
        system_instructions: "",
        output_format_hint: "Return plain text or structured JSON as appropriate.",
        allowed_handoff_targets_csv: "",
        approval_required: false,
      });
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="text-xl font-semibold">Agent Management</div>
        <div className="text-sm text-gray-600">Manage custom agents and enable/disable participants per workspace.</div>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-semibold">Agents</div>
            <div className="text-xs text-gray-500">{agents.filter((a) => a.is_active).length} enabled</div>
          </div>

          {agents.length === 0 ? (
            <div className="text-sm text-gray-600">No agents found.</div>
          ) : (
            <div className="space-y-3">
              {agents.map((a) => (
                <div key={a.id} className="rounded-md border bg-gray-50 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold">{a.role_title}</div>
                      <div className="text-xs text-gray-600">{a.name}</div>
                      <div className="mt-1 text-xs text-gray-700">{a.description}</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <span className="rounded-full bg-white px-2 py-0.5 text-xs border">{a.approval_required ? "Approval required" : "Auto"}</span>
                        <span className="rounded-full bg-white px-2 py-0.5 text-xs border">{a.is_active ? "Enabled" : "Disabled"}</span>
                      </div>
                    </div>

                    <button
                      onClick={() => onToggleActive(a)}
                      className={`rounded-md px-3 py-2 text-sm border ${
                        a.is_active ? "bg-white hover:bg-gray-50" : "bg-gray-50 hover:bg-white"
                      }`}
                    >
                      {a.is_active ? "Disable" : "Enable"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="mb-3 text-sm font-semibold">Create Custom Agent</div>
          <div className="space-y-3">
            <input
              className="w-full rounded-md border bg-white px-3 py-2 text-sm"
              placeholder="Name (e.g., Security Auditor)"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            />
            <input
              className="w-full rounded-md border bg-white px-3 py-2 text-sm"
              placeholder="Role title (e.g., Reviewer)"
              value={form.role_title}
              onChange={(e) => setForm((p) => ({ ...p, role_title: e.target.value }))}
            />
            <textarea
              className="w-full rounded-md border bg-white px-3 py-2 text-sm"
              rows={3}
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
            />
            <textarea
              className="w-full rounded-md border bg-white px-3 py-2 text-sm"
              rows={4}
              placeholder="System instructions"
              value={form.system_instructions}
              onChange={(e) => setForm((p) => ({ ...p, system_instructions: e.target.value }))}
            />
            <input
              className="w-full rounded-md border bg-white px-3 py-2 text-sm"
              placeholder="Output format hint"
              value={form.output_format_hint}
              onChange={(e) => setForm((p) => ({ ...p, output_format_hint: e.target.value }))}
            />
            <input
              className="w-full rounded-md border bg-white px-3 py-2 text-sm"
              placeholder="Allowed handoff targets (comma-separated role titles)"
              value={form.allowed_handoff_targets_csv}
              onChange={(e) => setForm((p) => ({ ...p, allowed_handoff_targets_csv: e.target.value }))}
            />
            <label className="flex items-center justify-between gap-3 text-sm">
              <span>Approval required</span>
              <input
                type="checkbox"
                checked={form.approval_required}
                onChange={(e) => setForm((p) => ({ ...p, approval_required: e.target.checked }))}
              />
            </label>

            <button
              disabled={
                loading ||
                !form.name.trim() ||
                !form.role_title.trim() ||
                !form.description.trim() ||
                !form.system_instructions.trim()
              }
              onClick={onCreate}
              className="w-full rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create Agent"}
            </button>
          </div>
          <div className="mt-3 text-xs text-gray-500">
            Tip: in this demo, workflow routing uses role title keywords to decide which agent executes each step.
          </div>
        </div>
      </div>
    </div>
  );
}

