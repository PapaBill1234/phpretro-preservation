import type { AccountViewModel } from "./viewModel.js";

export function AccountView({ model }: { model: AccountViewModel }) {
  const hasWidgets = model.widgets.length > 0;
  return (
    <section data-account-view="account.v1">
      <div data-account-field="id">{model.profile.id}</div>
      <div data-account-field="username">{model.profile.username}</div>
      <div data-account-field="motto">{model.profile.motto}</div>
      <div data-account-field="look">{model.profile.look}</div>
      <div data-account-field="gender">{model.profile.gender}</div>
      <div data-account-field="accountCreated">{model.profile.accountCreated}</div>
      <div data-account-status={model.status}>{model.status}</div>
      <div data-account-widgets={hasWidgets ? "present" : "empty"}>
        {hasWidgets ? model.widgets.map((widget) => <div key={widget.name} data-account-widget={widget.name}>{widget.value}</div>) : "No widgets available"}
      </div>
    </section>
  );
}
