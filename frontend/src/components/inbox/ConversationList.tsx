import type { Conversation } from "@/lib/api";

export function ConversationList({
  conversations,
  selectedId,
  onSelect,
}: {
  conversations: Conversation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <div className="flex flex-col gap-1 overflow-y-auto p-2">
      {conversations.length === 0 ? (
        <div className="px-2 py-6 text-center text-sm text-gray-500">No conversations yet.</div>
      ) : (
        conversations.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => onSelect(c.id)}
            className={`rounded-lg border px-3 py-2.5 text-left text-sm transition-colors ${
              selectedId === c.id
                ? "border-brand-300 bg-brand-50 shadow-sm"
                : "border-transparent bg-white hover:border-gray-200 hover:bg-gray-50"
            }`}
          >
            <div className="font-medium text-gray-900 line-clamp-1">{c.title || `Conversation #${c.id}`}</div>
            <div className="mt-0.5 text-xs text-gray-500">
              {c.linked_workflow_run_id ? `Run #${c.linked_workflow_run_id}` : "No workflow"}
            </div>
          </button>
        ))
      )}
    </div>
  );
}
