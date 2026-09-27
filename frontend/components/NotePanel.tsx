"use client";

import { useEffect, useRef } from "react";

import type { Note } from "@/lib/api";

/**
 * The note split into its numbered sentences using the stored offsets, so a highlight
 * covers exactly `text[start:end]`. `cited` sentences get a light mark; `focused` ones
 * (the selected suggestion's evidence) get a strong mark plus an outline, not color alone.
 */
export function NotePanel({
  note,
  cited,
  focused,
}: {
  note: Note;
  cited: Set<number>;
  focused: Set<number>;
}) {
  const refs = useRef(new Map<number, HTMLSpanElement>());
  const first = Math.min(...focused);

  useEffect(() => {
    if (Number.isFinite(first)) {
      refs.current.get(first)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [first]);

  const parts: React.ReactNode[] = [];
  let pos = 0;
  for (const s of note.sentences) {
    if (s.start > pos) parts.push(note.text.slice(pos, s.start));
    const isFocused = focused.has(s.n);
    const isCited = cited.has(s.n);
    parts.push(
      <span
        key={s.n}
        ref={(el) => {
          if (el) refs.current.set(s.n, el);
        }}
        data-sentence={s.n}
        data-highlighted={isFocused ? "true" : undefined}
        title={`Sentence ${s.n} · ${s.section}`}
        className={
          isFocused
            ? "rounded bg-amber-200 outline outline-2 outline-amber-500"
            : isCited
              ? "rounded bg-amber-50"
              : undefined
        }
      >
        <sup className={`mr-0.5 text-[10px] ${isFocused ? "font-bold" : "text-slate-400"}`}>
          {s.n}
        </sup>
        {note.text.slice(s.start, s.end)}
      </span>,
    );
    pos = s.end;
  }
  if (pos < note.text.length) parts.push(note.text.slice(pos));

  return (
    <section aria-label="Note" className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-3 flex items-baseline justify-between text-xs text-slate-500">
        <span>
          Visit {note.visit_date} · {note.patient_type} patient
        </span>
        <span>{note.sentences.length} sentences</span>
      </div>
      <p className="whitespace-pre-wrap text-sm leading-7">{parts}</p>
    </section>
  );
}
