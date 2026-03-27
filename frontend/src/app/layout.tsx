import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "agentops-cloud-platform",
  description: "Cloud-based multi-agent workflow orchestration (portfolio demo).",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="border-b bg-white">
            <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div className="flex flex-wrap items-center gap-6">
                <Link href="/dashboard" className="text-sm font-semibold text-gray-900 hover:text-brand-700">
                  agentops-cloud-platform
                </Link>
                <nav className="flex items-center gap-4 text-sm text-gray-600">
                  <Link href="/dashboard" className="hover:text-brand-700">
                    Dashboard
                  </Link>
                  <Link href="/inbox" className="font-medium text-brand-700 hover:text-brand-800">
                    Inbox
                  </Link>
                </nav>
              </div>
              <div className="text-xs text-gray-500">Portfolio demo</div>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}

