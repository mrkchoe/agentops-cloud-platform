export function ChannelBadge({ channel }: { channel: "whatsapp" | "web" | string }) {
  const isWa = channel === "whatsapp";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        isWa ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"
      }`}
    >
      {isWa ? "WhatsApp" : "Web"}
    </span>
  );
}
