"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listActivityLogs, listWorkspaces, createWorkspace, type ActivityLog, type Workspace } from "@/lib/api";
import type { ReactNode } from "react";

function Card({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border bg-white p-4 shadow-sm">{children}</div>;
}

export default function DashboardPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activity, setActivity] = useState<ActivityLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [ws, logs] = await Promise.all([listWorkspaces(), listActivityLogs(20)]);
        if (!cancelled) {
          setWorkspaces(ws);
          setActivity(logs);
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onCreateWorkspace() {
    setError(null);
    try {
      const created = await createWorkspace({ name: newWorkspaceName.trim() });
      setWorkspaces((prev) => [created, ...prev]);
      setNewWorkspaceName("");
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-xl font-semibold">Dashboard</div>
          <div className="text-sm text-gray-600">Workspaces, workflows, and activity.</div>
        </div>

        <div className="flex items-center gap-2">
          <input
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
            placeholder="New workspace name"
            className="w-72 rounded-md border bg-white px-3 py-2 text-sm"
          />
          <button
            onClick={onCreateWorkspace}
            disabled={!newWorkspaceName.trim()}
            className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-semibold text-gray-900">Workspaces</div>
            <Link className="text-sm text-brand-700 hover:underline" href="/dashboard">
              Refresh
            </Link>
          </div>

          {workspaces.length === 0 ? (
            <div className="text-sm text-gray-600">No workspaces yet.</div>
          ) : (
            <div className="space-y-3">
              {workspaces.map((ws) => (
                <Link key={ws.id} href={`/workspaces/${ws.id}`} className="block">
                  <div className="rounded-md border bg-gray-50 p-3 hover:bg-white">
                    <div className="text-sm font-semibold">{ws.name}</div>
                    <div className="text-xs text-gray-500">Created {new Date(ws.created_at).toLocaleDateString()}</div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-semibold text-gray-900">Recent Activity</div>
          </div>
          {activity.length === 0 ? (
            <div className="text-sm text-gray-600">No activity yet.</div>
          ) : (
            <div className="space-y-3">
              {activity.slice(0, 12).map((log) => (
                <div key={log.id} className="rounded-md border bg-white p-3">
                  <div className="text-xs font-semibold text-gray-700">{log.event_type}</div>
                  <div className="mt-1 text-sm text-gray-900">{log.message}</div>
                  <div className="mt-1 text-xs text-gray-500">{new Date(log.created_at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

