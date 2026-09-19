"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowLeft } from "lucide-react";
import { Shell, ErrorBox } from "@/components/Shell";
import { api, Session, errorText } from "@/lib/api";
import { useSession } from "@/lib/store";
import type { ReplayFrame } from "@/components/Replay";
const Replay = dynamic(() => import("@/components/Replay"), { ssr: false });
type Data = {
  session: Session;
  frames: ReplayFrame[];
  repetitions: {
    seq: number;
    captured_at: string;
    source: string;
    device_id: string;
    authoritative: boolean;
  }[];
  checkin: { pain: number; effort: number; notes: string } | null;
};
type Report = {
  model: string;
  version: string;
  metrics_used: Record<string, unknown>;
  content: { summary: string; observations: string[]; limitations: string[] };
};
export default function Review({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const token = useSession((s) => s.token);
  const [data, setData] = useState<Data>();
  const [report, setReport] = useState<Report>();
  const [error, setError] = useState("");
  const [reportError, setReportError] = useState("");
  useEffect(() => {
    if (token) {
      api<Data>(`/sessions/${id}/replay`)
        .then(setData)
        .catch((e) => setError(errorText(e)));
      api<Report>(`/sessions/${id}/report`)
        .then(setReport)
        .catch((e) => setReportError(errorText(e)));
    }
  }, [id, token]);
  return (
    <Shell>
      <Link className="row note" href="/dashboard">
        <ArrowLeft size={15} />
        Patient directory
      </Link>
      <div className="heading" style={{ marginTop: 24 }}>
        <div className="eyebrow">THE MOVEMENT AND THE MOMENT</div>
        <h1 style={{ marginTop: 12 }}>Session review</h1>
        <p className="muted">
          {data
            ? new Date(data.session.created_at).toLocaleString()
            : "Loading session…"}{" "}
          · {data?.session.mode || ""}{" "}
          <span className="pill">
            {data?.session.is_synthetic ? "SIMULATED DATA" : "Captured session"}
          </span>
        </p>
      </div>
      <ErrorBox message={error} />
      <div className="grid">
        <section className="card stack">
          <h2>A closer look at the movement</h2>
          {data?.frames.length ? (
            <Replay
              frames={data.frames}
              repetitions={data.repetitions}
              gapMs={Number(data.session.config_snapshot.gap_ms) || 750}
            />
          ) : (
            <p className="empty">No movement frames have been saved.</p>
          )}
        </section>
        <div className="stack">
          <section className="card stack">
            <h2>Session observations</h2>
            <ErrorBox message={reportError} />
            {report ? (
              <>
                <p className="muted">{report.content.summary}</p>
                {report.content.observations?.map((o, i) => (
                  <p key={i} className="muted">
                    {o}
                  </p>
                ))}
                <div className="grid">
                  {Object.entries(report.metrics_used).map(([key, value]) => (
                    <div key={key}>
                      <p className="eyebrow">{key.replaceAll("_", " ")}</p>
                      <p style={{ marginTop: 5 }}>{String(value)}</p>
                    </div>
                  ))}
                </div>
                <p className="note">
                  Report: {report.model} · {report.version}
                </p>
                {report.content.limitations?.map((l, i) => (
                  <p className="note" key={i}>
                    {l}
                  </p>
                ))}
              </>
            ) : (
              <p className="muted">
                Saved movement remains available independently of report
                generation.
              </p>
            )}
          </section>
          <section className="card stack">
            <h2>In the patient’s words</h2>
            {data?.checkin ? (
              <>
                <div className="row">
                  <span className="pill">
                    Reported pain {data.checkin.pain}/10
                  </span>
                  <span className="pill">
                    Reported effort {data.checkin.effort}/10
                  </span>
                </div>
                <p className="muted">
                  {data.checkin.notes || "No additional notes provided."}
                </p>
                <p className="note">
                  Self-reported feedback, separate from measured movement.
                </p>
              </>
            ) : (
              <p className="muted">No patient check-in yet.</p>
            )}
          </section>
        </div>
      </div>
    </Shell>
  );
}
