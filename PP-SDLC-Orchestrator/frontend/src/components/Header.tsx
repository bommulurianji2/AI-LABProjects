"use client";

import Link from "next/link";
import { useState } from "react";
import { useCurrentUser } from "@/lib/current-user-context";
import { ApiError } from "@/lib/api";

function initialsFor(email: string): string {
  const name = email.split("@")[0] ?? email;
  const parts = name.split(/[._-]/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return letters.toUpperCase();
}

export default function Header() {
  const { users, currentUserId, currentUser, loading, error, setCurrentUserId, addUser } = useCurrentUser();
  const [showAdd, setShowAdd] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Reviewer");
  const [busy, setBusy] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    setAddError(null);
    try {
      await addUser(email.trim(), role.trim() || "Reviewer");
      setEmail("");
      setShowAdd(false);
    } catch (err) {
      setAddError(err instanceof ApiError ? err.message : "Could not add user.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <header className="site-header">
      <Link href="/" className="brand">
        <span className="brand-mark">PP</span>
        <span>PP-SDLC-Orchestrator</span>
      </Link>

      <div className="identity">
        {error && <span className="error">{error}</span>}
        {!error && loading && <span className="muted">Loading…</span>}
        {!error && !loading && (
          <>
            <span className="identity-avatar">{currentUser ? initialsFor(currentUser.email) : "?"}</span>
            <div>
              <div className="identity-label">Acting as</div>
              {users.length > 0 ? (
                <select value={currentUserId} onChange={(e) => setCurrentUserId(e.target.value)}>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email} ({u.role})
                    </option>
                  ))}
                </select>
              ) : (
                <span className="muted">No users yet</span>
              )}
            </div>
            <button type="button" className="secondary" onClick={() => setShowAdd((v) => !v)}>
              {showAdd ? "Cancel" : "+ New"}
            </button>
          </>
        )}
      </div>

      {showAdd && (
        <form
          onSubmit={handleAdd}
          className="row"
          style={{
            position: "absolute",
            right: "1.5rem",
            top: "100%",
            marginTop: "0.5rem",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            boxShadow: "var(--shadow-md)",
            padding: "0.85rem",
            zIndex: 20,
          }}
        >
          <div className="field" style={{ marginBottom: 0 }}>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.test"
              disabled={busy}
              autoFocus
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Role" disabled={busy} />
          </div>
          <button type="submit" disabled={busy || !email.trim()}>
            {busy ? "Adding…" : "Add"}
          </button>
          {addError && <p className="error">{addError}</p>}
        </form>
      )}
    </header>
  );
}
