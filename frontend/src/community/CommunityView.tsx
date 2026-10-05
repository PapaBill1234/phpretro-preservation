import type { CommunityViewModel } from "./viewModel.js";

export function CommunityView({ model }: { model: CommunityViewModel }) {
  const empty = model.rooms.length + model.discussions.length + model.news.length + model.tags.length === 0;
  return <section data-community-view="community.v1">
    {empty ? <p data-community-empty="true">No community content.</p> : <>
      <ul data-community-list="rooms">{model.rooms.map((room) => <li key={room.id}>{room.name}</li>)}</ul>
      <ul data-community-list="discussions">{model.discussions.map((discussion) => <li key={discussion.id}>{discussion.title}</li>)}</ul>
      <ul data-community-list="news">{model.news.map((item) => <li key={item.id}>{item.title}</li>)}</ul>
      <ul data-community-list="tags">{model.tags.map((tag) => <li key={tag.tag}>{tag.tag} ({tag.quantity})</li>)}</ul>
    </>}
  </section>;
}