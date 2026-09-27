"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmCard } from "@/components/EmCard";
import { GapList } from "@/components/GapList";
import { NotePanel } from "@/components/NotePanel";
import { SuggestionCard } from "@/components/SuggestionCard";
import { api, ApiError, describeError, type NoteHistory, type ReviewEvent } from "@/lib/api";

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const [history, setHistory] = useState<NoteHistory | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<unknown>(null);
  // A clicked or keyboard-focused card stays selected until another card is chosen;
  // hovering previews a card's evidence without changing the selection.
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const focusId = hoverId ?? pickedId;
  const [showHidden, setShowHidden] = useState(false);

  const load = useCallback(async () => {
    try {
      setHistory(await api.getHistory(id));
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err : new ApiError(0, "UNKNOWN_ERROR", String(err)));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function analyze() {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      await api.analyzeNote(id);
    } catch (err) {
      setAnalyzeError(err);
    } finally {
      await load(); // a failed analysis is stored too, so history shows it
      setAnalyzing(false);
    }
  }

  const analysis = history?.analyses[0] ?? null;
  const visible = (analysis?.suggestions ?? []).filter((s) => s.confidence !== "not_suggested");
  const hidden = (analysis?.suggestions ?? []).filter((s) => s.confidence === "not_suggested");
  const shown = showHidden ? [...visible, ...hidden] : visible;

  // Latest review per suggestion of the current analysis is the current decision.
  const decisions = useMemo(() => {
    const latest = new Map<string, ReviewEvent>();
    for (const r of history?.reviews ?? []) {
      if (r.analysis_id === analysis?.analysis_id) latest.set(r.suggestion_id, r);
    }
    return latest;
  }, [history, analysis]);

  const cited = new Set(shown.flatMap((s) => s.evidence));
  const focused = new Set(shown.find((s) => s.suggestion_id === focusId)?.evidence ?? []);

  if (loadError?.errorCode === "NOTE_NOT_FOUND") {
    return (
      <div className="mx-auto max-w-xl rounded-lg border border-slate-200 bg-white p-6">
        <h1 className="text-lg font-semibold">Note not found</h1>
        <p className="mt-2 text-sm text-slate-600">No note has the id {id}.</p>
        <Link href="/" className="mt-4 inline-block text-sm underline">
          Enter a new note
        </Link>
      </div>
    );
  }
  if (loadError) {
    return (
      <p role="alert" className="rounded bg-red-50 p-4 text-sm text-red-700">
        {describeError(loadError)} ({loadError.errorCode})
      </p>
    );
  }
  if (!history) {
    return (
      <div aria-busy="true" className="grid animate-pulse gap-6 lg:grid-cols-2">
        <div className="h-64 rounded-lg bg-slate-200" />
        <div className="h-64 rounded-lg bg-slate-200" />
      </div>
    );
  }

  const failed = analysis?.status === "failed" ? analysis : null;
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="space-y-4 lg:sticky lg:top-6 lg:self-start">
        <NotePanel note={history.note} cited={cited} focused={focused} />
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={analyze}
            disabled={analyzing}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {analyzing ? "Analyzing…" : analysis ? "Analyze again" : "Analyze"}
          </button>
          <p aria-live="polite" className="text-xs text-slate-500">
            {analyzing
              ? "Reading the note, finding candidate codes and checking rules. This can take up to 2.5 minutes."
              : analysis
                ? `Last analysis ${new Date(analysis.created_at).toLocaleString()} · ${analysis.model}`
                : "Not analyzed yet."}
          </p>
        </div>
        {(history.previous_versions.length > 0 || history.later_versions.length > 0) && (
          <p className="text-xs text-slate-500">
            Versions:{" "}
            {[...history.previous_versions, history.note.id, ...history.later_versions].map((v, i) => (
              <span key={v}>
                {i > 0 && " → "}
                {v === history.note.id ? (
                  <strong>this</strong>
                ) : (
                  <Link href={`/notes/${v}`} className="underline">
                    v{i + 1}
                  </Link>
                )}
              </span>
            ))}
          </p>
        )}
      </div>

      <div className="space-y-4">
        {analyzeError !== null && !failed && (
          <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-700">
            {describeError(analyzeError)}
            {analyzeError instanceof ApiError && ` (${analyzeError.errorCode})`}
          </p>
        )}

        {failed && (
          <section role="alert" aria-label="Analysis failed" className="rounded-lg border border-red-200 bg-red-50 p-4">
            <h2 className="text-sm font-semibold text-red-800">Analysis failed</h2>
            <p className="mt-1 text-sm text-red-700">
              {describeError(new ApiError(503, failed.error?.code ?? "UNKNOWN_ERROR", failed.error?.message ?? ""))}
            </p>
            <p className="mt-1 font-mono text-xs text-red-700">
              {failed.error?.code} at {failed.error?.stage}: {failed.error?.message}
            </p>
            <p className="mt-2 text-xs text-red-700">
              Nothing partial is shown. Use “Analyze again” to retry; this attempt stays in the history.
            </p>
          </section>
        )}

        {analysis && !failed && (
          <>
            <div className="flex items-baseline justify-between">
              <h2 className="text-sm font-semibold">
                Suggestions ({visible.length})
                {analysis.model_errors > 0 && (
                  <span className="ml-2 font-normal text-slate-500">
                    {analysis.model_errors} model output(s) dropped by validation
                  </span>
                )}
              </h2>
              {hidden.length > 0 && (
                <button onClick={() => setShowHidden((v) => !v)} className="text-xs underline">
                  {showHidden ? "Hide" : "Show"} {hidden.length} not suggested
                </button>
              )}
            </div>
            {shown.length === 0 && (
              <p className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-600">
                No codes suggested for this note.
              </p>
            )}
            {shown.map((s) => (
              <SuggestionCard
                key={s.suggestion_id}
                analysisId={analysis.analysis_id}
                suggestion={s}
                gaps={analysis.gaps.filter((g) => s.gap_ids.includes(g.gap_id))}
                decision={decisions.get(s.suggestion_id)}
                selected={pickedId === s.suggestion_id}
                onHover={(on) => setHoverId(on ? s.suggestion_id : null)}
                onPick={() => setPickedId(s.suggestion_id)}
                onReviewed={load}
              />
            ))}
            <GapList gaps={analysis.gaps} />
            <EmCard em={analysis.em} />
          </>
        )}
      </div>
    </div>
  );
}
