"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Shell, ErrorBox } from "@/components/Shell";
import { api, errorText } from "@/lib/api";
export default function Pair() {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();
  async function join(e: React.FormEvent) {
    e.preventDefault();
    try {
      const p = await api<{
        device_token: string;
        session_id: string;
        device_id: string;
      }>("/devices/pair", { code, label: "Phone browser", expected_source: "phone" });
      sessionStorage.setItem(`device-${p.session_id}`, JSON.stringify(p));
      router.push(`/patient/sessions/${p.session_id}`);
    } catch (e) {
      setError(errorText(e));
    }
  }
  return (
    <Shell patient>
      <div className="heading">
        <div className="eyebrow">CONNECT YOUR DEVICES</div>
        <h1 style={{ marginTop: 12 }}>Let’s pair up.</h1>
        <p className="muted">
          Enter the temporary pairing code from your session.
        </p>
      </div>
      <form className="card form" onSubmit={join}>
        <label>
          Pairing code
          <input
            autoComplete="off"
            className="code"
            required
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
          />
        </label>
        <ErrorBox message={error} />
        <button className="btn">Connect to session</button>
      </form>
    </Shell>
  );
}
