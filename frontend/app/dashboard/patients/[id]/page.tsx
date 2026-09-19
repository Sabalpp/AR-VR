"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import * as Dialog from "@radix-ui/react-dialog";
import * as Tabs from "@radix-ui/react-tabs";
import { Plus, ArrowLeft, ArrowUpRight } from "lucide-react";
import { Shell, ErrorBox } from "@/components/Shell";
import {
  api,
  Patient,
  Assignment,
  Exercise,
  Session,
  errorText,
} from "@/lib/api";
import { useSession } from "@/lib/store";
export default function Detail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const token = useSession((s) => s.token);
  const [patient, setPatient] = useState<Patient>();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [exercise, setExercise] = useState("");
  const [reps, setReps] = useState(5);
  const [reach, setReach] = useState(145);
  const [rest, setRest] = useState(95);
  const [busy, setBusy] = useState(false);
  async function refresh() {
    try {
      const [p, a, e, s] = await Promise.all([
        api<Patient>(`/patients/${id}`),
        api<Assignment[]>(`/patients/${id}/assignments`),
        api<Exercise[]>("/exercises"),
        api<Session[]>(`/patients/${id}/sessions`),
      ]);
      setPatient(p);
      setAssignments(a);
      setExercises(e);
      setSessions(s);
      setExercise(e[0]?.id || "");
    } catch (e) {
      setError(errorText(e));
    }
  }
  useEffect(() => {
    if (token) void refresh();
  }, [token, id]);
  async function assign(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/assignments", {
        patient_id: id,
        exercise_definition_id: exercise,
        repetitions: reps,
        config: { phone_reach_deg: reach, phone_return_deg: rest },
      });
      setOpen(false);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Shell>
      <Link className="row note" href="/dashboard">
        <ArrowLeft size={15} />
        All patients
      </Link>
      <div className="heading" style={{ marginTop: 24 }}>
        <div className="row between">
          <div>
            <div className="eyebrow">PATIENT OVERVIEW</div>
            <h1 style={{ marginTop: 10 }}>
              {patient?.name || "Patient workspace"}
            </h1>
            <p className="muted">A plan for today. A record of every step.</p>
          </div>
          <span className="pill">
            {patient?.is_fictional ? "Fictional demo patient" : "Patient"}
          </span>
        </div>
      </div>
      <ErrorBox message={error} />
      <Tabs.Root defaultValue="plan">
        <Tabs.List className="tab-list">
          <Tabs.Trigger className="tab" value="plan">
            Assigned plan
          </Tabs.Trigger>
          <Tabs.Trigger className="tab" value="sessions">
            Session history ({sessions.length})
          </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="plan">
          <section className="card">
            <div className="row between">
              <h2>Home exercise plan</h2>
              <Dialog.Root open={open} onOpenChange={setOpen}>
                <Dialog.Trigger asChild>
                  <button className="btn">
                    <Plus size={16} />
                    Assign exercise
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="dialog-overlay" />
                  <Dialog.Content className="dialog">
                    <Dialog.Title asChild>
                      <h2>Make the next step clear.</h2>
                    </Dialog.Title>
                    <Dialog.Description
                      className="muted"
                      style={{ marginTop: 8, marginBottom: 22 }}
                    >
                      Configure an observable movement target for this patient.
                      These demonstration criteria are not clinical norms.
                    </Dialog.Description>
                    <form className="form" onSubmit={assign}>
                      <label>
                        Exercise
                        <select
                          value={exercise}
                          onChange={(e) => setExercise(e.target.value)}
                        >
                          {exercises.map((e) => (
                            <option key={e.id} value={e.id}>
                              {e.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Repetitions
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={reps}
                          onChange={(e) => setReps(+e.target.value)}
                          required
                        />
                      </label>
                      <div className="grid">
                        <label>
                          Extension threshold (°)
                          <input
                            type="number"
                            min={100}
                            max={180}
                            value={reach}
                            onChange={(e) => setReach(+e.target.value)}
                            required
                          />
                        </label>
                        <label>
                          Return threshold (°)
                          <input
                            type="number"
                            min={20}
                            max={130}
                            value={rest}
                            onChange={(e) => setRest(+e.target.value)}
                            required
                          />
                        </label>
                      </div>
                      <ErrorBox message={error} />
                      <button className="btn" disabled={busy || !exercise}>
                        {busy ? "Saving…" : "Add to patient’s plan"}
                      </button>
                      <Dialog.Close asChild>
                        <button type="button" className="btn secondary">
                          Cancel
                        </button>
                      </Dialog.Close>
                    </form>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
            </div>
            {assignments.map((a) => (
              <div className="patient-row" key={a.id}>
                <div className="avatar">
                  <ArrowUpRight size={20} />
                </div>
                <div className="grow">
                  <h3>
                    {a.exercise_name ||
                      exercises.find((e) => e.id === a.exercise_definition_id)
                        ?.name ||
                      "Seated reach"}
                  </h3>
                  <p className="muted">
                    {a.repetitions} repetitions · Phone or headset
                  </p>
                  <p className="note">Assignment {a.id.slice(0, 8)}</p>
                </div>
                <span className="pill">Assigned</span>
              </div>
            ))}
            {!assignments.length && (
              <p className="empty">
                Add an exercise to begin this patient’s home plan.
              </p>
            )}
          </section>
          <div className="hero" style={{ marginTop: 24 }}>
            <h3>Ready on their phone</h3>
            <p className="muted" style={{ marginTop: 8 }}>
              The patient signs into this same public HTTPS address. New
              assignments appear in Today’s plan.
            </p>
          </div>
        </Tabs.Content>
        <Tabs.Content value="sessions">
          <section className="card">
            <h2>Movement, in context</h2>
            {sessions.map((s) => (
              <Link
                href={`/dashboard/sessions/${s.id}`}
                className="patient-row"
                key={s.id}
              >
                <div className="grow">
                  <h3>{new Date(s.created_at).toLocaleString()}</h3>
                  <p className="note">
                    {s.mode} ·{" "}
                    {s.is_synthetic ? "SIMULATED DATA" : "Captured session"}
                  </p>
                </div>
                <span className="pill">{s.state.status}</span>
                <ArrowUpRight size={18} />
              </Link>
            ))}
            {!sessions.length && (
              <p className="empty">
                Completed sessions will appear here for review.
              </p>
            )}
          </section>
        </Tabs.Content>
      </Tabs.Root>
    </Shell>
  );
}
