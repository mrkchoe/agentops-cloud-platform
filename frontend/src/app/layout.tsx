import type { Metadata } from "next";
import type { ReactNode } from "react";
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
            <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
              <div className="text-sm font-semibold text-gray-900">agentops-cloud-platform</div>
              <div className="text-xs text-gray-500">Portfolio demo</div>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}

