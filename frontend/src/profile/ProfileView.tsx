import type { ProfileViewModel } from "./viewModel.js";

export function ProfileView({ model }: { model: ProfileViewModel }) {
  return (
    <section data-profile-view="profile.v1">
      <div data-profile-field="id">{model.profile.id}</div>
      <div data-profile-field="username">{model.profile.username}</div>
      <div data-profile-field="motto">{model.profile.motto}</div>
      <div data-profile-field="look">{model.profile.look}</div>
      <div data-profile-field="gender">{model.profile.gender}</div>
      <div data-profile-field="accountCreated">{model.profile.accountCreated}</div>
      <nav data-profile-tab={model.tab} aria-label="Profile tabs" />
    </section>
  );
}
