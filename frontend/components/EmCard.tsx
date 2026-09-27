import type { AnalysisResult } from "@/lib/api";

export function EmCard({ em }: { em: AnalysisResult["em"] }) {
  return (
    <section aria-label="E/M level" className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold">E/M level</h2>
      {em == null ? (
        <p className="mt-2 text-xs text-slate-500">E/M calculation arrives in a later milestone.</p>
      ) : em.code ? (
        <p className="mt-2 font-mono text-lg">
          {em.code} <span className="text-xs text-slate-500">MDM {em.mdm_level}</span>
        </p>
      ) : (
        <p className="mt-2 text-xs">
          No E/M level: missing {em.missing.join(", ") || "MDM elements"}.
        </p>
      )}
    </section>
  );
}
