import type { HomeViewModel } from "../viewModel.js";

export const localizationKeys = ["siteTitle", "welcome", "navigationHome"] as const;
export type LocalizationKey = (typeof localizationKeys)[number];

export type LocalizationMessages = Readonly<Record<LocalizationKey, string>>;

export type LocalizationCatalog = Readonly<{
  locale: string;
  messages: LocalizationMessages;
}>;

export type MissingKeyBehavior = "placeholder" | "throw";

export const defaultLocale = "en" as const;
export const syntheticCatalogs: readonly LocalizationCatalog[] = [
  {
    locale: "en",
    messages: {
      siteTitle: "PHPRetro",
      welcome: "Synthetic starter view",
      navigationHome: "Home"
    }
  },
  {
    locale: "fr",
    messages: {
      siteTitle: "PHPRetro",
      welcome: "Vue de démarrage synthétique",
      navigationHome: "Accueil"
    }
  }
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function validateCatalog(value: unknown): value is LocalizationCatalog {
  if (!isRecord(value) || typeof value.locale !== "string" || value.locale.trim() === "") {
    return false;
  }
  const messages = value.messages;
  if (!isRecord(messages)) return false;
  return localizationKeys.every((key) => typeof messages[key] === "string") &&
    Object.keys(messages).every((key) => (localizationKeys as readonly string[]).includes(key));
}

export function localeFallbackChain(requestedLocale: string, fallback: string = defaultLocale): string[] {
  const requested = requestedLocale.trim().toLowerCase();
  const fallbackLocale = fallback.trim().toLowerCase();
  const language = requested.split("-")[0];
  return [...new Set([requested, language, fallbackLocale])].filter(Boolean);
}

export function resolveLocale(
  requestedLocale: string,
  availableLocales: readonly string[],
  fallback: string = defaultLocale
): string | undefined {
  const byNormalized = new Map(availableLocales.map((locale) => [locale.toLowerCase(), locale]));
  for (const candidate of localeFallbackChain(requestedLocale, fallback)) {
    const match = byNormalized.get(candidate);
    if (match) return match;
  }
  return undefined;
}

export function selectCatalog(
  catalogs: readonly LocalizationCatalog[],
  requestedLocale: string,
  fallback: string = defaultLocale
): LocalizationCatalog | undefined {
  const validCatalogs = catalogs.filter(validateCatalog);
  const locale = resolveLocale(requestedLocale, validCatalogs.map((catalog) => catalog.locale), fallback);
  return validCatalogs.find((catalog) => catalog.locale === locale);
}

export function missingKey(key: string): string {
  return `[missing:${key}]`;
}

export function translate(
  catalog: LocalizationCatalog | undefined,
  key: LocalizationKey,
  behavior: MissingKeyBehavior = "placeholder"
): string {
  const value = catalog?.messages[key];
  if (typeof value === "string") return value;
  if (behavior === "throw") throw new Error(`missing localization key: ${key}`);
  return missingKey(key);
}

export function createLocalizedHomeViewModel(
  catalogs: readonly LocalizationCatalog[],
  requestedLocale: string,
  fallback: string = defaultLocale,
  missingBehavior: MissingKeyBehavior = "placeholder"
): HomeViewModel & { locale: string } {
  const catalog = selectCatalog(catalogs, requestedLocale, fallback);
  return {
    version: "home.v1",
    locale: catalog?.locale ?? requestedLocale,
    siteTitle: translate(catalog, "siteTitle", missingBehavior),
    welcome: translate(catalog, "welcome", missingBehavior),
    navigation: [{ label: translate(catalog, "navigationHome", missingBehavior), href: "/" }]
  };
}
