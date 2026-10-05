import { createRoot } from "react-dom/client";
import { AccountView } from "./account/AccountView.js";
import { CommunityView } from "./community/CommunityView.js";
import { ProfileView } from "./profile/ProfileView.js";
import { communityFixture } from "./community/viewModel.js";
import { acceptAccountViewModel } from "./account/viewModel.js";
import { acceptProfileViewModel } from "./profile/viewModel.js";
import { presentHome } from "./home/viewModel.js";

const profile = acceptProfileViewModel({
  version: "profile.v1",
  profile: { id: 1, username: "DemoUser", motto: "Synthetic profile", look: "development-placeholder", gender: "M", accountCreated: "2026-01-01T00:00:00Z" },
  tab: 1
});
const account = acceptAccountViewModel({ version: "account.v1", profile: profile.profile, status: "synthetic", widgets: [] });
const home = presentHome({ ownerId: 1, username: "DemoUser", showHome: true, publicContent: "Synthetic public home" });

function App() {
  return <main><h1>PHPRetro</h1><section data-home-view="home.v1"><h2>{home.username}</h2><p>{home.publicContent}</p></section><ProfileView model={profile} /><AccountView model={account} /><CommunityView model={communityFixture} /></main>;
}

const root = document.querySelector("#root");
if (!root) throw new Error("missing #root");
createRoot(root).render(<App />);
