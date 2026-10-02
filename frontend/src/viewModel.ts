export type HomeViewModel = {
  version: "home.v1";
  siteTitle: string;
  welcome: string;
  navigation: readonly { label: string; href: string }[];
};

export const syntheticHomeViewModel: HomeViewModel = {
  version: "home.v1",
  siteTitle: "PHPRetro",
  welcome: "Synthetic starter view",
  navigation: [{ label: "Home", href: "/" }]
};

export function acceptHomeViewModel(value: unknown): HomeViewModel {
  if (!value || typeof value !== "object" || (value as { version?: unknown }).version !== "home.v1") {
    throw new Error("unsupported view-model version");
  }
  const model = value as HomeViewModel;
  if (typeof model.siteTitle !== "string" || typeof model.welcome !== "string" || !Array.isArray(model.navigation)) {
    throw new Error("malformed home view-model");
  }
  return model;
}
