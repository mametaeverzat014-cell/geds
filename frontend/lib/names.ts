/**
 * Human-readable names for graph identifiers.
 *
 * The engine speaks ISO3 + industry slug ("TWN:semiconductors") because that is
 * what the data sources key on, but nobody reading the page thinks in ISO codes.
 * Everything user-facing goes through here.
 */

import type { Lang } from "./ui-context";

const COUNTRY: Record<string, { en: string; ru: string }> = {
  CHN: { en: "China", ru: "Китай" },
  DEU: { en: "Germany", ru: "Германия" },
  IND: { en: "India", ru: "Индия" },
  JPN: { en: "Japan", ru: "Япония" },
  KOR: { en: "South Korea", ru: "Южная Корея" },
  MEX: { en: "Mexico", ru: "Мексика" },
  MYS: { en: "Malaysia", ru: "Малайзия" },
  NLD: { en: "Netherlands", ru: "Нидерланды" },
  THA: { en: "Thailand", ru: "Таиланд" },
  TWN: { en: "Taiwan", ru: "Тайвань" },
  USA: { en: "United States", ru: "США" },
  VNM: { en: "Vietnam", ru: "Вьетнам" },
  // v3 (OECD ICIO) adds many more economies; anything unmapped falls back to
  // the raw code rather than guessing a name.
  GBR: { en: "United Kingdom", ru: "Великобритания" },
  FRA: { en: "France", ru: "Франция" },
  ITA: { en: "Italy", ru: "Италия" },
  ESP: { en: "Spain", ru: "Испания" },
  CAN: { en: "Canada", ru: "Канада" },
  BRA: { en: "Brazil", ru: "Бразилия" },
  AUS: { en: "Australia", ru: "Австралия" },
  RUS: { en: "Russia", ru: "Россия" },
  SGP: { en: "Singapore", ru: "Сингапур" },
  IDN: { en: "Indonesia", ru: "Индонезия" },
  TUR: { en: "Türkiye", ru: "Турция" },
  POL: { en: "Poland", ru: "Польша" },
  KAZ: { en: "Kazakhstan", ru: "Казахстан" },
  SAU: { en: "Saudi Arabia", ru: "Саудовская Аравия" },
  ARE: { en: "UAE", ru: "ОАЭ" },
  CHE: { en: "Switzerland", ru: "Швейцария" },
  SWE: { en: "Sweden", ru: "Швеция" },
  BEL: { en: "Belgium", ru: "Бельгия" },
  AUT: { en: "Austria", ru: "Австрия" },
  CZE: { en: "Czechia", ru: "Чехия" },
  IRL: { en: "Ireland", ru: "Ирландия" },
  PHL: { en: "Philippines", ru: "Филиппины" },
  ZAF: { en: "South Africa", ru: "Южная Африка" },
  ROW: { en: "Rest of world", ru: "Остальной мир" },
};

const INDUSTRY: Record<string, { en: string; ru: string }> = {
  semiconductors: { en: "semiconductors", ru: "полупроводники" },
  automotive: { en: "automotive", ru: "автопром" },
  electronics: { en: "electronics", ru: "электроника" },
  electronics_c26: { en: "electronics", ru: "электроника" },
  aerospace: { en: "aerospace", ru: "авиакосмос" },
  shipping: { en: "shipping", ru: "морские перевозки" },
  consumer_goods: { en: "consumer goods", ru: "потребительские товары" },
  energy: { en: "energy", ru: "энергетика" },
  agriculture: { en: "agriculture", ru: "сельское хозяйство" },
  chemicals: { en: "chemicals", ru: "химия" },
};

const CHOKEPOINT: Record<string, { en: string; ru: string }> = {
  Suez: { en: "Suez Canal", ru: "Суэцкий канал" },
  Panama: { en: "Panama Canal", ru: "Панамский канал" },
  Malacca: { en: "Strait of Malacca", ru: "Малаккский пролив" },
  Hormuz: { en: "Strait of Hormuz", ru: "Ормузский пролив" },
  TaiwanStrait: { en: "Taiwan Strait", ru: "Тайваньский пролив" },
};

/** "TWN" → "Taiwan" / "Тайвань". Unknown codes are returned unchanged. */
export function countryName(iso3: string, lang: Lang): string {
  return COUNTRY[iso3]?.[lang] ?? iso3;
}

/** "semiconductors" → "semiconductors" / "полупроводники". */
export function industryName(slug: string, lang: Lang): string {
  return INDUSTRY[slug]?.[lang] ?? slug.replace(/_/g, " ");
}

/**
 * "TWN:semiconductors" → "Taiwan · semiconductors" / "Тайвань · полупроводники"
 * "CP:Suez"            → "Suez Canal" / "Суэцкий канал"
 * Anything unrecognised is passed through so the UI never shows a blank.
 */
export function nodeName(nodeId: string, lang: Lang): string {
  if (!nodeId) return nodeId;
  const [head, tail] = nodeId.split(":");
  if (!tail) return nodeId;
  if (head === "CP") {
    return CHOKEPOINT[tail]?.[lang] ?? tail;
  }
  return `${countryName(head, lang)} · ${industryName(tail, lang)}`;
}

/** Short form for tight spaces: "Taiwan · semis" style is avoided; just the country. */
export function nodeCountryLabel(nodeId: string, lang: Lang): string {
  const [head, tail] = nodeId.split(":");
  if (head === "CP") return CHOKEPOINT[tail]?.[lang] ?? tail;
  return countryName(head, lang);
}
