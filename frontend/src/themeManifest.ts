export const THEME_API_VERSION = "theme.v1" as const;
export const VIEW_MODEL_VERSION = "home.v1" as const;

export type ThemeManifest = {
  apiVersion: typeof THEME_API_VERSION;
  id: string;
  version: string;
  entry: "react";
  component: "StarterShell";
  viewModels: readonly [typeof VIEW_MODEL_VERSION];
  capabilities: readonly ["presentation"];
};

export const phpretroManifest: ThemeManifest = {
  apiVersion: THEME_API_VERSION,
  id: "phpretro",
  version: "0.1.0",
  entry: "react",
  component: "StarterShell",
  viewModels: [VIEW_MODEL_VERSION],
  capabilities: ["presentation"]
};

export function validateThemeManifest(value: unknown): value is ThemeManifest {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ThemeManifest>;
  return candidate.apiVersion === THEME_API_VERSION &&
    typeof candidate.id === "string" && candidate.id.length > 0 &&
    typeof candidate.version === "string" && candidate.entry === "react" &&
    candidate.component === "StarterShell" &&
    Array.isArray(candidate.viewModels) && candidate.viewModels.length === 1 && candidate.viewModels[0] === VIEW_MODEL_VERSION &&
    Array.isArray(candidate.capabilities) && candidate.capabilities.length === 1 && candidate.capabilities[0] === "presentation";
}
