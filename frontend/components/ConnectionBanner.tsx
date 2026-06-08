"use client";

import { useEffect, useState } from "react";

import { api, API_BASE } from "@/lib/api";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

/**
 * Surfaces backend connectivity instead of failing silently.
 *
 * Every data fetch in the app does `.catch(() => {})`, so when the backend is
 * unreachable the UI just sits in an empty "loading…" state that reads as fake
 * /mock data. This component polls the liveness probe (`/healthz`) every 10s,
 * drives `backendStatus` in the store (which also colours the ribbon dot), and
 * shows a dismissible banner the moment the backend cannot be reached.
 *
 * Reachability = the host returns *any* HTTP response. A non-2xx (e.g. a stale
 * deploy that 404s on `/healthz`) still counts as online, so the banner only
 * fires on a true network failure — never on a reachable-but-imperfect backend.
 */
export default function ConnectionBanner() {
  const status = useSimStore((s) => s.backendStatus);
  const setStatus = useSimStore((s) => s.setBackendStatus);
  const { lang } = useUI();
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let alive = true;
    const ping = () =>
      api
        .healthz()
        .then((reachable) => {
          if (!alive) return;
          if (reachable) {
            setStatus("online");
          } else {
            setStatus("offline");
            setDismissed(false); // re-surface on a fresh outage
          }
        })
        .catch(() => {
          // healthz() resolves to a boolean and never rejects, but stay
          // defensive: treat anything unexpected as offline (conservative).
          if (alive) {
            setStatus("offline");
            setDismissed(false);
          }
        });
    ping();
    const id = setInterval(ping, 10_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [setStatus]);

  if (status !== "offline" || dismissed) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-md border border-sev-5/40 bg-sev-5/10 px-4 py-3 text-sm"
    >
      <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-sev-5 animate-pulse" />
      <div className="min-w-0 flex-1 text-text-secondary leading-relaxed">
        <span className="font-semibold text-sev-5">
          {lang === "en" ? "Backend unreachable." : "Бэкенд недоступен."}
        </span>{" "}
        {lang === "en" ? (
          <>
            The app cannot reach the API at{" "}
            <code className="text-text-primary">{API_BASE}</code>. Start it locally
            (<code className="text-text-primary">uvicorn app.main:app --reload</code> in{" "}
            <code className="text-text-primary">backend/</code>), or set{" "}
            <code className="text-text-primary">NEXT_PUBLIC_API_URL</code> to a deployed
            backend. Panels stay empty until it responds.
          </>
        ) : (
          <>
            Приложение не может подключиться к API по адресу{" "}
            <code className="text-text-primary">{API_BASE}</code>. Запустите его локально
            (<code className="text-text-primary">uvicorn app.main:app --reload</code> в папке{" "}
            <code className="text-text-primary">backend/</code>) или задайте{" "}
            <code className="text-text-primary">NEXT_PUBLIC_API_URL</code> для развёрнутого
            бэкенда. Панели будут пустыми, пока он не ответит.
          </>
        )}
      </div>
      <button
        onClick={() => setDismissed(true)}
        aria-label={lang === "en" ? "Dismiss" : "Закрыть"}
        className="shrink-0 rounded px-2 text-text-muted hover:text-text-primary transition"
      >
        ×
      </button>
    </div>
  );
}
