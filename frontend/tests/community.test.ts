import { strict as assert } from "node:assert";
import test from "node:test";
import { CommunityView } from "../src/community/CommunityView.js";
import { acceptCommunityViewModel, communityFixture, emptyCommunityFixture } from "../src/community/viewModel.js";

test("renders bounded community lists and tags", () => {
  const model = acceptCommunityViewModel(communityFixture);
  const view = CommunityView({ model });
  assert.equal(view.props["data-community-view"], "community.v1");
  assert.equal(model.rooms.length, 1);
  assert.equal(model.tags[0].tag, "retro");
});

test("renders a clean empty state", () => {
  const view = CommunityView({ model: emptyCommunityFixture });
  assert.equal(view.props.children.props["data-community-empty"], "true");
});

test("rejects malformed and over-bounded payloads", () => {
  assert.throws(() => acceptCommunityViewModel({ ...communityFixture, rooms: [{ id: 0 }] }), /malformed/);
  assert.throws(() => acceptCommunityViewModel({ ...communityFixture, tags: Array.from({ length: 21 }, () => communityFixture.tags[0]) }), /malformed/);
  assert.throws(() => acceptCommunityViewModel({ ...communityFixture, version: "community.v2" }), /unsupported/);
});