import Link from "next/link";

export default function HomePage() {
  return (
    <div className="space-y-2">
      <div className="text-lg font-semibold">agentops-cloud-platform</div>
      <div className="text-sm text-gray-600">Open the dashboard to manage workspaces and workflows.</div>
      <Link className="inline-flex rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700" href="/dashboard">
        Go to Dashboard
      </Link>
    </div>
  );
}

