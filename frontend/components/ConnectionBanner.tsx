"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

export default function ConnectionBanner() {
  const status = useSimStore((s) => s.backendStatus);
  const setStatus = useSimStore((s) => s.setBackendStatus);
  const { lang } = useUI();
  const [dismissed, setDismissed] = useState(false);
  const [wakingSecs, setWakingSecs] = useState(0);
  const firstOfflineAt = useRef<number | null>(null);

  // Poll /healthz — aggressively (3 s) while offline to catch the wake-up
  // quickly; back off to 30 s once online.
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;

    const ping = () => {
      api.healthz().then((reachable) => {
        if (!alive) return;
        if (reachable) {
          setStatus("online");
          firstOfflineAt.current = null;
          timer = setTimeout(ping, 30_000);
        } else {
          setStatus("offline");
          setDismissed(false);
          if (firstOfflineAt.current == null) firstOfflineAt.current = Date.now();
          timer = setTimeout(ping, 3_000);
        }
      }).catch(() => {
        if (!alive) return;
        setStatus("offline");
        setDismissed(false);
        if (firstOfflineAt.current == null) firstOfflineAt.current = Date.now();
        timer = setTimeout(ping, 3_000);
      });
    };

    ping();
    return () => { alive = false; clearTimeout(timer); };
  }, [setStatus]);

  // Tick the "waking for N s" counter while offline.
  useEffect(() => {
    if (status !== "offline") { setWakingSecs(0); return; }
    const id = setInterval(() => {
      setWakingSecs(
        firstOfflineAt.current ? Math.floor((Date.now() - firstOfflineAt.current) / 1000) : 0
      );
    }, 1_000);
    return () => clearInterval(id);
  }, [status]);

  if (status !== "offline" || dismissed) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-md border border-sev-5/40 bg-sev-5/10 px-4 py-3 text-sm"
    >
      <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-sev-5 animate-pulse" />
      <div className="min-w-0 flex-1 text-text-secondary leading-relaxed">
        <span className="font-semibold text-sev-5">
          {lang === "en" ? "Service is starting up…" : "Сервис запускается…"}
        </span>{" "}
        {lang === "en" ? (
          <>
            The server is waking from sleep — free-tier hosting pauses after 15 min of inactivity.
            First load takes <strong className="text-text-primary">20–30 s</strong>. Retrying automatically
            {wakingSecs > 0 && <span className="text-text-muted num"> ({wakingSecs} s)</span>}.
          </>
        ) : (
          <>
            Сервер просыпается после сна — бесплатный хостинг засыпает через 15 мин без запросов.
            Первый запуск занимает <strong className="text-text-primary">20–30 с</strong>. Идут автоматические повторы
            {wakingSecs > 0 && <span className="text-text-muted num"> ({wakingSecs} с)</span>}.
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
