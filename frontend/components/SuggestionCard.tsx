"use client";

import { useState } from "react";

import {
  api,
  ApiError,
  type Gap,
  type ReviewEvent,
  type ReviewRequest,
  type Suggestion,
} from "@/lib/api";

const OUTCOME_STYLE: Record<string, string> = {
  pass: "bg-emerald-50 text-emerald-800",
  needs_review: "bg-amber-50 text-amber-800",
  fail: "bg-red-50 text-red-800",
};

const CONFIDENCE_STYLE: Record<string, string> = {
  strong: "bg-emerald-100 text-emerald-900",
  review: "bg-amber-100 text-amber-900",
  not_suggested: "bg-slate-200 text-slate-700",
};

type Mode = "idle" | "edit" | "reject";

export function SuggestionCard({
  analysisId,
  suggestion: s,
  gaps,
  decision,
  selected,
  locked,
  onHover,
  onPick,
  onReviewed,
}: {
  analysisId: string;
  suggestion: Suggestion;
  gaps: Gap[];
  decision: ReviewEvent | undefined;
  selected: boolean;
  /** True while a new analysis runs: this card's analysis is about to be replaced. */
  locked: boolean;
  onHover: (on: boolean) => void;
  onPick: () => void;
  onReviewed: () => void;
}) {
  const [mode, setMode] = useState<Mode>("idle");
  const [code, setCode] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(body: ReviewRequest) {
    setBusy(true);
    setError(null);
    try {
      await api.review(analysisId, s.suggestion_id, body);
      setMode("idle");
      setCode("");
      setReason("");
      onReviewed();
    } catch (err) {
      setError(err instanceof ApiError ? `${err.errorCode}: ${err.message}` : "Review failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article
      aria-label={`Suggestion ${s.code}`}
      data-code={s.code}
      tabIndex={0}
      aria-current={selected ? "true" : undefined}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      onClick={onPick}
      onFocus={onPick}
      className={`cursor-pointer rounded-lg border bg-white p-4 outline-none focus-visible:ring-2 focus-visible:ring-slate-400 ${selected ? "border-amber-500 ring-2 ring-amber-200" : "border-slate-200"}`}
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-lg font-semibold">{s.code}</p>
          <p className="text-sm text-slate-700">{s.description}</p>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-1">
          {s.added_by_rule && (
            <span className="rounded bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-900">
              Added by rule {s.added_by_rule}
            </span>
          )}
          <span className={`rounded px-2 py-0.5 text-xs font-medium ${CONFIDENCE_STYLE[s.confidence]}`}>
            {s.confidence.replace("_", " ")}
          </span>
        </div>
      </header>

      <p className="mt-2 text-xs text-slate-500">
        {s.system} · evidence: sentence{s.evidence.length === 1 ? "" : "s"}{" "}
        {s.evidence.join(", ")}
      </p>

      {s.rule_results.length > 0 && (
        <ul className="mt-3 space-y-1">
          {s.rule_results.map((r, i) => (
            <li key={`${r.rule_id}-${i}`} className={`rounded px-2 py-1 text-xs ${OUTCOME_STYLE[r.outcome]}`}>
              <span className="font-semibold">{r.rule_id}</span> {r.outcome.replace("_", " ")}:{" "}
              {r.message} <span className="opacity-70">({r.source_ref})</span>
            </li>
          ))}
        </ul>
      )}

      {gaps.length > 0 && (
        <ul className="mt-2 space-y-1">
          {gaps.map((g) => (
            <li key={g.gap_id} className="rounded border border-amber-300 px-2 py-1 text-xs">
              Gap · {g.missing}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 border-t border-slate-100 pt-3" aria-live="polite">
        {locked && (
          <p className="mb-2 text-xs text-slate-500">Review is paused while the note is re-analyzed.</p>
        )}
        {decision ? (
          <p data-testid="decision" className="mb-2 text-xs">
            Decision: <span className="font-semibold">{decision.action}</span>
            {decision.replacement_code && <> to {decision.replacement_code}</>}
            {decision.reason && <> · “{decision.reason}”</>}
          </p>
        ) : (
          <p className="mb-2 text-xs text-slate-500">Not reviewed yet</p>
        )}

        {mode === "idle" && (
          <div className="flex gap-2">
            <button
              disabled={busy || locked}
              onClick={() => send({ action: "accept" })}
              className="rounded bg-emerald-700 px-3 py-1 text-xs font-medium text-white disabled:opacity-40"
            >
              Accept
            </button>
            <button
              disabled={busy || locked}
              onClick={() => setMode("edit")}
              className="rounded border border-slate-300 px-3 py-1 text-xs font-medium"
            >
              Edit
            </button>
            <button
              disabled={busy || locked}
              onClick={() => setMode("reject")}
              className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-700"
            >
              Reject
            </button>
          </div>
        )}

        {mode !== "idle" && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(
                mode === "edit"
                  ? { action: "edit", replacement_code: code.trim(), reason: reason.trim() || null }
                  : { action: "reject", reason: reason.trim() },
              );
            }}
            className="space-y-2"
          >
            {mode === "edit" && (
              <input
                aria-label={`Replacement code for ${s.code}`}
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="Replacement code, e.g. N18.31"
                required
                className="w-full rounded border border-slate-300 px-2 py-1 font-mono text-xs"
              />
            )}
            <input
              aria-label={`Reason for ${s.code}`}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={mode === "reject" ? "Reason (required)" : "Reason (optional)"}
              required={mode === "reject"}
              className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
            />
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={busy || locked}
                className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-40"
              >
                {mode === "edit" ? "Save edit" : "Confirm reject"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("idle");
                  setError(null);
                }}
                className="rounded px-3 py-1 text-xs"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {error && (
          <p role="alert" className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
            {error}
          </p>
        )}
      </div>
    </article>
  );
}
