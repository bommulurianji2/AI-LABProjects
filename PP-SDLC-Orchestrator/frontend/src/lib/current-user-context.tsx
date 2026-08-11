"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { User } from "./types";

const STORAGE_KEY = "pp-sdlc-current-user-id";

interface CurrentUserContextValue {
  users: User[];
  currentUserId: string;
  currentUser: User | null;
  loading: boolean;
  error: string | null;
  setCurrentUserId: (id: string) => void;
  addUser: (email: string, role: string) => Promise<User>;
}

const CurrentUserContext = createContext<CurrentUserContextValue | null>(null);

// A stand-in for real auth (there is none yet — see the implementation
// ledger). This is app-wide "who's acting right now" state: it drives both
// the header identity switcher and every review submission's reviewer_id,
// so the two can never drift out of sync the way the old per-page reviewer
// picker could.
export function CurrentUserProvider({ children }: { children: React.ReactNode }) {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUserId, setCurrentUserIdState] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const data = await api.listUsers();
        if (ignore) return;
        setUsers(data);
        setError(null);
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored && data.some((u) => u.id === stored)) {
          setCurrentUserIdState(stored);
        } else if (data.length > 0) {
          setCurrentUserIdState(data[0].id);
        }
      } catch (err) {
        if (!ignore) setError(err instanceof ApiError ? err.message : "Could not load users.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  function setCurrentUserId(id: string) {
    setCurrentUserIdState(id);
    window.localStorage.setItem(STORAGE_KEY, id);
  }

  async function addUser(email: string, role: string): Promise<User> {
    const user = await api.createUser(email, role);
    setUsers((prev) => (prev.some((u) => u.id === user.id) ? prev : [...prev, user]));
    setCurrentUserId(user.id);
    return user;
  }

  const currentUser = users.find((u) => u.id === currentUserId) ?? null;

  return (
    <CurrentUserContext.Provider
      value={{ users, currentUserId, currentUser, loading, error, setCurrentUserId, addUser }}
    >
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser(): CurrentUserContextValue {
  const ctx = useContext(CurrentUserContext);
  if (!ctx) {
    throw new Error("useCurrentUser must be used within a CurrentUserProvider");
  }
  return ctx;
}
