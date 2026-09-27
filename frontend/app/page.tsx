"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ApiError, type NoteCreate } from "@/lib/api";
import samples from "@/lib/samples.json";

const MIN = 20;
const MAX = 20_000;

export default function NewNotePage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [visitDate, setVisitDate] = useState("2026-10-15");
  const [patientType, setPatientType] = useState<NoteCreate["patient_type"]>("established");
  const [sample, setSample] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function loadSample(label: string) {
    setSample(label);
    const found = samples.find((s) => s.label === label);
    if (!found) return;
    setText(found.text);
    setVisitDate(found.visit_date);
    setPatientType(found.patient_type === "new" ? "new" : "established");
    setError(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const note = await api.createNote({
        text,
        visit_date: visitDate,
        patient_type: patientType,
      });
      router.push(`/notes/${note.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.errorCode}: ${err.message}` : "Could not save.");
      setSaving(false);
    }
  }

  const tooShort = text.trim().length < MIN;
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold">New outpatient note</h1>
      <p className="mt-1 text-sm text-slate-600">
        Paste a synthetic note or load a sample. The note is analyzed into ICD-10-CM suggestions,
        each with the sentences that support it, rule checks, and documentation gaps.
      </p>

      <form onSubmit={submit} className="mt-6 space-y-4 rounded-lg border border-slate-200 bg-white p-6">
        <div>
          <label htmlFor="sample" className="block text-sm font-medium">
            Load sample note
          </label>
          <select
            id="sample"
            value={sample}
            onChange={(e) => loadSample(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Choose a synthetic sample…</option>
            {samples.map((s) => (
              <option key={s.label} value={s.label}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="text" className="block text-sm font-medium">
            Note text
          </label>
          <textarea
            id="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            maxLength={MAX}
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 font-mono text-sm"
            placeholder="Assessment: Type 2 diabetes mellitus with chronic kidney disease stage 3."
          />
          <p className="mt-1 text-xs text-slate-500">
            {text.length.toLocaleString()} / {MAX.toLocaleString()} characters (at least {MIN})
          </p>
        </div>

        <div className="flex flex-wrap gap-6">
          <div>
            <label htmlFor="visit-date" className="block text-sm font-medium">
              Visit date
            </label>
            <input
              id="visit-date"
              type="date"
              value={visitDate}
              onChange={(e) => setVisitDate(e.target.value)}
              required
              className="mt-1 rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <fieldset>
            <legend className="block text-sm font-medium">Patient</legend>
            <div className="mt-2 flex gap-4 text-sm">
              {(["established", "new"] as const).map((t) => (
                <label key={t} className="flex items-center gap-1">
                  <input
                    type="radio"
                    name="patient-type"
                    checked={patientType === t}
                    onChange={() => setPatientType(t)}
                  />
                  {t === "new" ? "New" : "Established"}
                </label>
              ))}
            </div>
          </fieldset>
        </div>

        {error && (
          <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={saving || tooShort}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save note"}
        </button>
      </form>
    </div>
  );
}
