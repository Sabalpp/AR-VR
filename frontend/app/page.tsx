"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { Brand, ErrorBox } from "@/components/Shell";
import { api, errorText } from "@/lib/api";
import { useSession } from "@/lib/store";
export default function Login() {
  const router = useRouter();
  const setAuth = useSession((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await api<{
        access_token: string;
        user: { id: string; email: string; role: string };
      }>("/auth/login", { email, password });
      setAuth(data.access_token, data.user);
      router.push(data.user.role === "therapist" ? "/dashboard" : "/patient");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login">
      <section className="login-art">
        <Brand />
        <div>
          <div className="eyebrow">A little further, together</div>
          <h1>
            Care that moves
            <br />
            with you.
          </h1>
          <p className="muted" style={{ marginTop: 24, maxWidth: 390 }}>
            A shared space for your home exercises, your therapist, and the
            progress you make along the way.
          </p>
        </div>
        <div className="orbit" />
        <p className="note">CONNECTED PHYSICAL THERAPY · RESEARCH PROTOTYPE</p>
      </section>
      <section className="login-form">
        <div className="stack">
          <div>
            <div className="eyebrow" style={{ marginBottom: 12 }}>
              Welcome to Reach
            </div>
            <h2>Let’s take the next step.</h2>
            <p className="muted" style={{ marginTop: 10 }}>
              Sign in to your personal care workspace.
            </p>
          </div>
          <form onSubmit={submit} className="form">
            <label>
              Email address
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <ErrorBox message={error} />
            <button className="btn" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="card" style={{ background: "#f6f7f2", padding: 18 }}>
            <p className="eyebrow">Fictional demo accounts</p>
            <p className="note" style={{ marginTop: 8 }}>
              Local setup credentials are in the project README. Demo accounts
              contain fictional people; camera sessions capture your real
              movement.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
