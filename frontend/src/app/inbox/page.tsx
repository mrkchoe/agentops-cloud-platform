"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { listWorkspaces } from "@/lib/api";

export default function InboxRedirectPage() {
  const router = useRouter();
  const [msg, setMsg] = useState("Loading Inbox…");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ws = await listWorkspaces();
        if (cancelled) return;
        if (ws[0]) {
          router.replace(`/workspaces/${ws[0].id}/inbox`);
        } else {
          setMsg("No workspace found. Create one from the Dashboard first.");
        }
      } catch (e: unknown) {
        setMsg(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600 shadow-sm">
      {msg}
    </div>
  );
}
