"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatLabel } from "@/lib/format";
import type { Project } from "@/lib/types";

export default function HomePage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Reusable, unguarded — safe to call from an event handler (handleCreate
  // below) where the component is definitely still mounted.
  async function loadProjects() {
    try {
      setProjects(await api.listProjects());
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not reach the backend.");
    }
  }

  useEffect(() => {
    // The mount-time fetch needs its own cancellation guard: if the user
    // navigates away before it resolves, this must not call setState on an
    // unmounted component. See https://react.dev/learn/synchronizing-with-effects#fetching-data.
    let ignore = false;
    (async () => {
      try {
        const data = await api.listProjects();
        if (!ignore) {
          setProjects(data);
          setLoadError(null);
        }
      } catch (err) {
        if (!ignore) {
          setLoadError(err instanceof ApiError ? err.message : "Could not reach the backend.");
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    setCreating(true);
    setCreateError(null);
    try {
      await api.createProject(name.trim());
      setName("");
      await loadProjects();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Could not create the project.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="page stack">
      <section className="card">
        <h2>New project</h2>
        <form onSubmit={handleCreate} className="stack">
          <div className="field">
            <label htmlFor="project-name">Project name</label>
            <input
              id="project-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Employee Leave Request"
              disabled={creating}
            />
          </div>
          {createError && <p className="error">{createError}</p>}
          <button type="submit" disabled={creating || !name.trim()}>
            {creating ? "Creating…" : "Create project"}
          </button>
        </form>
      </section>

      <section>
        <h2>Projects</h2>
        {loadError && <p className="error">{loadError}</p>}
        {projects === null && !loadError && <p className="muted">Loading…</p>}
        {projects !== null && projects.length === 0 && <p className="muted">No projects yet.</p>}
        {projects?.map((project) => (
          <Link key={project.id} href={`/projects/${project.id}`} className="card card-link">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>{project.name}</strong>
              <span className="badge">{project.status}</span>
            </div>
            <p className="muted">
              {formatLabel(project.current_phase)} — {formatLabel(project.phase_status)}
            </p>
          </Link>
        ))}
      </section>
    </main>
  );
}
