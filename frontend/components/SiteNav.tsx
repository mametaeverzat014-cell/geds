"use client";

import { usePathname } from "next/navigation";

import { useUI } from "@/lib/ui-context";

/**
 * One navigation bar for every page, so the site reads as a single artefact
 * rather than four unrelated screens.
 *
 * Order is the argument the project wants to make, in sequence: see it work,
 * see it checked, see where it fails. A judge who reads left to right arrives
 * at the limitations having already been given the reasons to take them
 * seriously, which is the only order in which that page is persuasive rather
 * than deflating.
 *
 * Judge Mode sits first and is visually distinct because it is the entry point
 * for someone with ninety seconds.
 */

interface Item {
  href: string;
  en: string;
  ru: string;
  emphasis?: boolean;
}

const ITEMS: Item[] = [
  { href: "/judge", en: "Judge Mode", ru: "Режим жюри", emphasis: true },
  { href: "/", en: "Simulator", ru: "Симулятор" },
  { href: "/demo", en: "Track record", ru: "Track record" },
  { href: "/validation", en: "Validation", ru: "Валидация" },
  { href: "/limitations", en: "Limitations", ru: "Ограничения" },
];

export default function SiteNav() {
  const { lang, toggleLang, t } = useUI();
  const pathname = usePathname();
  const ru = lang === "ru";

  return (
    <nav className="flex items-center justify-between gap-3 border-b border-border-subtle pb-3">
      <div className="flex items-baseline gap-3 min-w-0">
        <a href="/" className="title-gradient text-lg sm:text-xl font-extrabold tracking-tight shrink-0">
          GEDS
        </a>
        {/* horizontal scroll rather than wrapping: on a narrow phone a wrapped
            nav pushes the page content below the fold before anything is read */}
        <div className="flex gap-1.5 overflow-x-auto no-scrollbar -mx-1 px-1">
          {ITEMS.map((it) => {
            const active = pathname === it.href;
            return (
              <a
                key={it.href}
                href={it.href}
                aria-current={active ? "page" : undefined}
                className={[
                  "btn-pill whitespace-nowrap text-[13px]",
                  active ? "is-active text-text-primary border-accent-cyan/50" : "",
                  it.emphasis && !active ? "text-accent-cyan border-accent-cyan/30" : "",
                ].join(" ")}
              >
                {ru ? it.ru : it.en}
              </a>
            );
          })}
        </div>
      </div>
      <button onClick={toggleLang} className="btn-pill shrink-0" aria-label="Switch language">
        {t("langBtn")}
      </button>
    </nav>
  );
}
