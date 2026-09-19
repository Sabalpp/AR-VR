"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Search, ChevronRight } from "lucide-react";
import { Shell, ErrorBox } from "@/components/Shell";
import { api, Patient, errorText } from "@/lib/api";
import { useSession } from "@/lib/store";
export default function Dashboard() {
  const token = useSession((s) => s.token);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => {
    if (token)
      api<Patient[]>("/patients")
        .then(setPatients)
        .catch((e) => setError(errorText(e)))
        .finally(() => setLoading(false));
  }, [token]);
  return (
    <Shell>
      <div className="heading">
        <div className="eyebrow">THE PEOPLE BEHIND THE PROGRESS</div>
        <h1 style={{ marginTop: 12 }}>Your patients</h1>
        <p className="muted">
          A clear view of their plan. A closer connection to their progress.
        </p>
      </div>
      <div className="hero row between" style={{ marginBottom: 28 }}>
        <div>
          <h2>Home practice, connected.</h2>
          <p className="muted" style={{ marginTop: 10 }}>
            Assign a movement, review a session, and bring what happens at home
            into your next conversation.
          </p>
        </div>
        <ArrowUpRight size={42} strokeWidth={1} />
      </div>
      <ErrorBox message={error} />
      <section className="card">
        <div className="row between wrap">
          <h2>
            Patient directory <span className="pill">{patients.length}</span>
          </h2>
          <label className="row">
            <Search size={16} />
            <input
              aria-label="Search patients"
              placeholder="Find a patient"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>
        {loading ? (
          <p className="empty">Loading your patients…</p>
        ) : (
          patients
            .filter((p) =>
              (p.name || "").toLowerCase().includes(query.toLowerCase()),
            )
            .map((p) => (
              <Link
                key={p.id}
                href={`/dashboard/patients/${p.id}`}
                className="patient-row"
              >
                <div className="avatar">
                  {(p.name || "P")
                    .split(" ")
                    .map((n) => n[0])
                    .slice(0, 2)
                    .join("")}
                </div>
                <div className="grow">
                  <h3>{p.name}</h3>
                  <p className="note">Home exercise plan</p>
                </div>
                <span className="pill">
                  {p.is_fictional ? "Fictional demo" : "Patient"}
                </span>
                <ChevronRight size={18} />
              </Link>
            ))
        )}
        {!loading && !patients.length && (
          <p className="empty">No patients assigned to this account.</p>
        )}
      </section>
    </Shell>
  );
}
