"use client";

import { CurrentUserProvider } from "@/lib/current-user-context";
import Header from "./Header";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <CurrentUserProvider>
      <Header />
      {children}
    </CurrentUserProvider>
  );
}
