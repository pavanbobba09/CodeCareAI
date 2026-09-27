import type { Gap } from "@/lib/api";

export function GapList({ gaps }: { gaps: Gap[] }) {
  return (
    <section aria-label="Documentation gaps" className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold">Documentation gaps ({gaps.length})</h2>
      {gaps.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">No gaps found.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {gaps.map((g) => (
            <li key={g.gap_id} className="rounded border border-amber-200 bg-amber-50/50 p-2 text-xs">
              <p className="font-medium">
                {g.kind} · {g.missing}{" "}
                <span className="font-normal text-slate-500">
                  ({g.severity}
                  {g.rule_id ? `, ${g.rule_id}` : ""}; affects {g.affects_codes.join(", ")})
                </span>
              </p>
              <p className="mt-1 text-slate-700">Query: {g.query_text}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
