export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
export const API_AUTH_TOKEN = process.env.NEXT_PUBLIC_API_AUTH_TOKEN || "dev-demo-token";
export const USER_ID = Number(process.env.NEXT_PUBLIC_USER_ID || "1");

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${API_AUTH_TOKEN}`,
      "x-user-id": String(USER_ID),
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

export type AgentTemplate = {
  id: number;
  name: string;
  role_title: string;
  description: string;
  system_instructions: string;
  allowed_tools: Record<string, unknown>;
  allowed_handoff_targets: string[];
  output_format_hint: string;
  approval_required: boolean;
  is_active: boolean;
};

export type Workspace = { id: number; name: string; created_at: string };
export type Agent = {
  id: number;
  workspace_id: number;
  template_id: number | null;
  name: string;
  role_title: string;
  description: string;
  output_format_hint: string;
  approval_required: boolean;
  is_active: boolean;
};

export type Workflow = {
  id: number;
  workspace_id: number;
  name: string;
  goal: string;
  require_human_approval: boolean;
  created_at: string;
};

export type WorkflowRun = {
  id: number;
  workflow_id: number;
  workspace_id: number;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  current_step_index: number;
  human_approval_required: boolean;
  shared_context: Record<string, unknown>;
  error: string | null;
};

export type Task = {
  id: number;
  kind: string;
  order_index: number;
  objective: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
};

export type TaskAssignment = {
  id: number;
  task_id: number;
  agent_id: number;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
};

export type Artifact = {
  id: number;
  task_id: number;
  agent_id: number;
  kind: string;
  content: string;
  created_at: string;
};

export type Approval = {
  id: number;
  workflow_run_id: number;
  checkpoint_kind: string;
  status: string;
  requested_at: string;
  decided_at: string | null;
  notes: string | null;
};

export type ActivityLog = {
  id: number;
  workspace_id: number;
  workflow_run_id: number | null;
  user_id: number;
  event_type: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type WorkflowRunDetail = {
  run: WorkflowRun;
  tasks: Task[];
  assignments: TaskAssignment[];
  artifacts: Artifact[];
  approvals: Approval[];
  activity_logs: ActivityLog[];
};

export async function listWorkspaces(): Promise<Workspace[]> {
  return apiRequest("/workspaces");
}

export async function createWorkspace(payload: { name: string }): Promise<Workspace> {
  return apiRequest("/workspaces", { method: "POST", body: JSON.stringify(payload) });
}

export async function listAgents(workspaceId: number): Promise<Agent[]> {
  return apiRequest(`/workspaces/${workspaceId}/agents`);
}

export async function createCustomAgent(workspaceId: number, payload: Omit<Agent, "id" | "workspace_id" | "template_id"> & { template_id?: null }): Promise<Agent> {
  return apiRequest(`/workspaces/${workspaceId}/agents`, { method: "POST", body: JSON.stringify(payload) });
}

export async function setAgentActive(agentId: number, payload: { is_active: boolean }): Promise<Agent> {
  return apiRequest(`/agents/${agentId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function listWorkflows(workspaceId: number): Promise<Workflow[]> {
  return apiRequest(`/workspaces/${workspaceId}/workflows`);
}

export async function createWorkflow(workspaceId: number, payload: { name: string; goal: string; participant_agent_ids: number[]; require_human_approval: boolean }): Promise<Workflow> {
  return apiRequest(`/workspaces/${workspaceId}/workflows`, { method: "POST", body: JSON.stringify(payload) });
}

export async function startWorkflowRun(workflowId: number): Promise<{ run_id: number }> {
  return apiRequest(`/workflows/${workflowId}/runs`, { method: "POST" });
}

export async function getWorkflowRunDetail(runId: number): Promise<WorkflowRunDetail> {
  return apiRequest(`/workflow-runs/${runId}`);
}

export async function listWorkflowRuns(workspaceId: number, limit = 10): Promise<WorkflowRun[]> {
  return apiRequest(`/workspaces/${workspaceId}/workflow-runs?limit=${limit}`);
}

export async function decideApproval(runId: number, approvalId: number, payload: { approved: boolean; notes?: string | null }): Promise<{ ok: boolean }> {
  return apiRequest(`/workflow-runs/${runId}/approvals/${approvalId}/decision`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listActivityLogs(limit = 20): Promise<ActivityLog[]> {
  return apiRequest(`/activity-logs?limit=${limit}`);
}

