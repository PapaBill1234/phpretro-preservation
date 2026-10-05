import { strict as assert } from "node:assert";
import test from "node:test";
import { AccountView } from "../src/account/AccountView.js";
import { acceptAccountViewModel } from "../src/account/viewModel.js";

const profile = {
  id: 7,
  username: "synthetic-user",
  motto: "test motto",
  look: "synthetic-look",
  gender: "M",
  accountCreated: "1970-01-01T00:01:40.000Z"
} as const;

const dashboard = {
  version: "account.v1",
  profile,
  status: "online",
  widgets: [{ name: "feed", value: "synthetic" }]
} as const;

test("renders the complete account dashboard without dropping fields", () => {
  const model = acceptAccountViewModel(dashboard);
  assert.deepEqual(model.profile, profile);
  assert.equal(model.status, "online");
  assert.deepEqual(model.widgets, [{ name: "feed", value: "synthetic" }]);
  const view = AccountView({ model });
  assert.equal(view.props["data-account-view"], "account.v1");
  assert.equal((view.props.children[6] as { props: { "data-account-status": string } }).props["data-account-status"], "online");
});

test("normalizes absent optional widgets to an empty state", () => {
  const model = acceptAccountViewModel({ ...dashboard, widgets: undefined });
  assert.deepEqual(model.widgets, []);
  const view = AccountView({ model });
  assert.equal((view.props.children[7] as { props: { "data-account-widgets": string } }).props["data-account-widgets"], "empty");
});

test("renders an explicit empty state when no widgets exist", () => {
  const model = acceptAccountViewModel({ ...dashboard, widgets: [] });
  assert.deepEqual(model.widgets, []);
  assert.equal((AccountView({ model }).props.children[7] as { props: { "data-account-widgets": string } }).props["data-account-widgets"], "empty");
});

test("rejects malformed dashboard payloads", () => {
  assert.throws(() => acceptAccountViewModel({ version: "account.v1", profile, status: "online", widgets: [{ name: "feed" }] }), /malformed/);
  assert.throws(() => acceptAccountViewModel({ ...dashboard, version: "account.v2" }), /unsupported/);
  assert.throws(() => acceptAccountViewModel({ ...dashboard, profile: { ...profile, id: 0 } }), /malformed/);
  assert.throws(() => acceptAccountViewModel({ ...dashboard, widgets: "feed" }), /malformed/);
});
