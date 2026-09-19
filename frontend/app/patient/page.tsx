"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, MoveUpRight, Link2 } from "lucide-react";
import { Shell, ErrorBox } from "@/components/Shell";
import { api, Assignment, Session, errorText } from "@/lib/api";
import { useSession } from "@/lib/store";
export default function Today() {
  const token = useSession((s) => s.token);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  useEffect(() => {
    if (token)
      api<Assignment[]>("/assignments")
        .then(setAssignments)
        .catch((e) => setError(errorText(e)));
  }, [token]);
  async function start(a: Assignment) {
    setBusy(true);
    try {
      const session = await api<Session>("/sessions", {
        assignment_id: a.id,
        mode: "phone",
        is_synthetic: false,
      });
      router.push(`/patient/sessions/${session.id}`);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }
  return (
    <Shell patient>
      <div className="heading">
        <div className="eyebrow">ONE MOVEMENT AT A TIME</div>
        <h1 style={{ marginTop: 12 }}>Today’s plan</h1>
        <p className="muted">Make a little room for yourself.</p>
      </div>
      <div className="hero" style={{ marginBottom: 24 }}>
        <MoveUpRight size={34} strokeWidth={1} />
        <h2 style={{ marginTop: 20 }}>Your pace. Your progress.</h2>
        <p className="muted" style={{ marginTop: 10 }}>
          Find a comfortable seat and a clear space. Your phone will help record
          your movement for your therapist.
        </p>
      </div>
      <ErrorBox message={error} />
      <div className="stack">
        {assignments.map((a) => (
          <article className="card stack" key={a.id}>
            <div className="row between">
              <span className="eyebrow">YOUR ASSIGNED EXERCISE</span>
              <span className="pill">{a.repetitions} reps</span>
            </div>
            <div>
              <h2>{a.exercise_name || "Seated reach"}</h2>
              <p className="muted" style={{ marginTop: 8 }}>
                Bend and extend your right elbow while comfortably seated. Keep
                your shoulder, elbow, and wrist in view.
              </p>
            </div>
            <button className="btn" disabled={busy} onClick={() => start(a)}>
              Set up my camera
              <ArrowRight size={18} />
            </button>
          </article>
        ))}
        {!assignments.length && !error && (
          <div className="card empty">
            Your therapist’s assignments will appear here.
          </div>
        )}
        <Link className="btn secondary" href="/patient/pair">
          <Link2 size={17} />
          Join an existing session
        </Link>
        <p className="note">
          Your camera stays on this device. Timestamped joint positions are sent
          to your care workspace for session review. Stop if you feel
          uncomfortable.
        </p>
      </div>
    </Shell>
  );
}
