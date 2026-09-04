"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import {
  api,
  isSnapshotActive,
  isSnapshotActiveServer,
  subscribeSnapshot,
  type SnapshotManifest,
} from "@/lib/api";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

/**
 * States the backend can be in, and what each one owes the reader.
 *
 *   online, no snapshot used   nothing — render nothing at all
 *   offline, snapshot serving  say the numbers are precomputed, name the commit
 *   offline, no snapshot yet   say the server is waking, retries are running
 *   online, snapshot on screen offer a reload; do NOT quietly relabel data as
 *                              live, because the panels still hold the snapshot
 *
 * The last case is the one worth being careful about. When the server wakes,
 * every value already rendered is still the snapshot's. Flipping the badge off
 * at that moment would be the cheap move and would make the page a liar for as
 * long as the visitor keeps scrolling, so the badge stays and becomes a button.
 */
export default function ConnectionBanner() {
  const status = useSimStore((s) => s.backendStatus);
  const setStatus = useSimStore((s) => s.setBackendStatus);
  const { lang } = useUI();
  const en = lang === "en";
  const [dismissed, setDismissed] = useState(false);
  const [wakingSecs, setWakingSecs] = useState(0);
  const [manifest, setManifest] = useState<SnapshotManifest | null>(null);
  const firstOfflineAt = useRef<number | null>(null);

  const usingSnapshot = useSyncExternalStore(
    subscribeSnapshot,
    isSnapshotActive,
    isSnapshotActiveServer,
  );

  // Poll /healthz — aggressively (3 s) while offline to catch the wake-up
  // quickly; back off to 30 s once online.
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;

    const offline = () => {
      if (!alive) return;
      setStatus("offline");
      setDismissed(false);
      if (firstOfflineAt.current == null) firstOfflineAt.current = Date.now();
      timer = setTimeout(ping, 3_000);
    };

    const ping = () => {
      api.healthz().then((reachable) => {
        if (!alive) return;
        if (reachable) {
          setStatus("online");
          firstOfflineAt.current = null;
          timer = setTimeout(ping, 30_000);
        } else {
          offline();
        }
      }).catch(offline);
    };

    ping();
    return () => { alive = false; clearTimeout(timer); };
  }, [setStatus]);

  // Tick the "waking for N s" counter while offline.
  useEffect(() => {
    if (status !== "offline") { setWakingSecs(0); return; }
    const id = setInterval(() => {
      setWakingSecs(
        firstOfflineAt.current ? Math.floor((Date.now() - firstOfflineAt.current) / 1000) : 0,
      );
    }, 1_000);
    return () => clearInterval(id);
  }, [status]);

  // Fetched only once something has actually been served from disk, so the
  // common path costs nothing.
  useEffect(() => {
    if (usingSnapshot && !manifest) api.snapshotManifest().then(setManifest);
  }, [usingSnapshot, manifest]);

  if (dismissed) return null;
  if (status === "online" && !usingSnapshot) return null;

  const live = status === "online";
  const tone = usingSnapshot
    ? "border-accent-violet/40 bg-accent-violet/10"
    : "border-sev-5/40 bg-sev-5/10";
  const dot = usingSnapshot ? "bg-accent-violet" : "bg-sev-5";
  const head = usingSnapshot ? "text-accent-violet" : "text-sev-5";

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-start gap-3 rounded-md border px-4 py-3 text-sm ${tone}`}
    >
      <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${dot} ${live ? "" : "animate-pulse"}`} />

      <div className="min-w-0 flex-1 space-y-1.5 leading-relaxed text-text-secondary">
        {usingSnapshot ? (
          <>
            <div>
              <span className={`font-semibold ${head}`}>
                {en ? "Showing a precomputed snapshot" : "Показан предвычисленный снимок"}
              </span>{" "}
              {en ? (
                <>
                  Every number on screen is real model output, produced by this same code
                  {manifest?.commit_short && (
                    <> at commit <span className="num text-text-primary">{manifest.commit_short}</span></>
                  )}
                  {" "}and shipped with the page — not live, and not invented.
                </>
              ) : (
                <>
                  Все числа на экране — реальный вывод модели, полученный этим же кодом
                  {manifest?.commit_short && (
                    <> на коммите <span className="num text-text-primary">{manifest.commit_short}</span></>
                  )}
                  {" "}и поставленный вместе со страницей: это не live-данные, но и не выдумка.
                </>
              )}
            </div>
            <div className="text-[13px] text-text-muted">
              {en
                ? "Panels that need live input — news signals, AI narrative, data freshness — stay empty until the server answers, because a frozen copy of those would mislead rather than merely be stale."
                : "Панели, которым нужны live-данные — новостные сигналы, ИИ-нарратив, свежесть данных — остаются пустыми до ответа сервера: замороженная копия там вводила бы в заблуждение, а не просто устаревала."}
            </div>
            {live ? (
              <button
                onClick={() => window.location.reload()}
                className="btn-pill border-accent-cyan/40 text-[12px] text-accent-cyan"
              >
                {en ? "Server is awake — load live data" : "Сервер проснулся — загрузить live-данные"}
              </button>
            ) : (
              <div className="text-[13px] text-text-muted">
                {en ? "Waking the live server" : "Идёт пробуждение сервера"}
                {wakingSecs > 0 && <span className="num"> ({wakingSecs}{en ? " s" : " с"})</span>}
                {en ? " — it replaces this automatically." : " — он заменит это автоматически."}
              </div>
            )}
          </>
        ) : (
          <div>
            <span className={`font-semibold ${head}`}>
              {en ? "Service is starting up…" : "Сервис запускается…"}
            </span>{" "}
            {en ? (
              <>
                The server is waking from sleep — free-tier hosting pauses after 15 min of inactivity.
                First load takes <strong className="text-text-primary">20–30 s</strong>. Retrying automatically
                {wakingSecs > 0 && <span className="num text-text-muted"> ({wakingSecs} s)</span>}.
              </>
            ) : (
              <>
                Сервер просыпается после сна — бесплатный хостинг засыпает через 15 мин без запросов.
                Первый запуск занимает <strong className="text-text-primary">20–30 с</strong>. Идут автоматические повторы
                {wakingSecs > 0 && <span className="num text-text-muted"> ({wakingSecs} с)</span>}.
              </>
            )}
          </div>
        )}
      </div>

      <button
        onClick={() => setDismissed(true)}
        aria-label={en ? "Dismiss" : "Закрыть"}
        className="shrink-0 rounded px-2 text-text-muted transition hover:text-text-primary"
      >
        ×
      </button>
    </div>
  );
}
