import type { ReactElement } from "react";
import type { HomeViewModel } from "./viewModel.js";

export function StarterShell({ model }: { model: HomeViewModel }): ReactElement {
  return <main data-theme="phpretro"><h1>{model.siteTitle}</h1><p>{model.welcome}</p></main>;
}
