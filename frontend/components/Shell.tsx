"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Users, Activity, LogOut } from "lucide-react";
import { restoreAuth, useSession } from "@/lib/store";
export function Brand() {
  return (
    <Link href="/" className="brand">
      <span className="brand-mark" />
      reach<span style={{ fontSize: 12, letterSpacing: 0 }}>PT</span>
    </Link>
  );
}
export function Shell({
  children,
  patient = false,
}: {
  children: React.ReactNode;
  patient?: boolean;
}) {
  const router = useRouter();
  const { user, logout } = useSession();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    restoreAuth();
    if (!useSession.getState().token) router.replace("/");
    else setReady(true);
  }, [router]);
  if (!ready) return <div className="empty">Opening your workspace…</div>;
  const signout = (
    <button
      className="btn secondary"
      aria-label="Sign out"
      onClick={() => {
        logout();
        router.push("/");
      }}
    >
      <LogOut size={16} />
    </button>
  );
  if (patient)
    return (
      <main className="phone-shell">
        <header className="row between phone-header">
          <Brand />
          {signout}
        </header>
        {children}
      </main>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        <Brand />
        <nav className="nav">
          <Link href="/dashboard" className="active">
            <Users size={18} />
            <span>Patients</span>
          </Link>
          <Link href="/">
            <Activity size={18} />
            <span>Switch account</span>
          </Link>
        </nav>
        <div className="footer-note">
          CONNECTED CARE
          <br />
          <br />
          Small movements.
          <br />
          Meaningful progress.
          <br />
          <br />
          Hackathon demonstration
          <br />
          Fictional patient records
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="eyebrow">Your care workspace</div>
          <div className="row">
            <span className="note">{user?.email}</span>
            {signout}
          </div>
        </header>
        {children}
        <p className="note" style={{ marginTop: 40 }}>
          Reach research prototype · Observable movement, human-led care
        </p>
      </main>
    </div>
  );
}
export function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div role="alert" className="error">
      {message}
    </div>
  ) : null;
}
