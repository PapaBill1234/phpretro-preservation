export type CommunityRoom = {
  id: number;
  name: string;
  description: string;
  owner: string;
};

export type CommunityDiscussion = { id: number; title: string; groupId: number };

export type CommunityNews = {
  id: number;
  title: string;
  summary: string;
  headerImage: string;
  date: string;
};

export type CommunityTag = { tag: string; quantity: number };

export type CommunityViewModel = {
  version: "community.v1";
  rooms: CommunityRoom[];
  discussions: CommunityDiscussion[];
  news: CommunityNews[];
  tags: CommunityTag[];
};

const MAX_ITEMS = 20;

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function boundedArray(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value) || value.length > MAX_ITEMS) throw new Error(`malformed community ${name}`);
  return value;
}

export function acceptCommunityViewModel(value: unknown): CommunityViewModel {
  if (!isRecord(value) || value.version !== "community.v1") {
    throw new Error("unsupported community view-model version");
  }
  const rooms = boundedArray(value.rooms, "rooms");
  const discussions = boundedArray(value.discussions, "discussions");
  const news = boundedArray(value.news, "news");
  const tags = boundedArray(value.tags, "tags");
  if (rooms.some((row) => !isRecord(row) || typeof row.id !== "number" || !Number.isInteger(row.id) || row.id <= 0 || typeof row.name !== "string" || typeof row.description !== "string" || typeof row.owner !== "string") ||
      discussions.some((row) => !isRecord(row) || typeof row.id !== "number" || !Number.isInteger(row.id) || row.id <= 0 || typeof row.title !== "string" || typeof row.groupId !== "number" || !Number.isInteger(row.groupId)) ||
      news.some((row) => !isRecord(row) || typeof row.id !== "number" || !Number.isInteger(row.id) || row.id <= 0 || typeof row.title !== "string" || typeof row.summary !== "string" || typeof row.headerImage !== "string" || typeof row.date !== "string") ||
      tags.some((row) => !isRecord(row) || typeof row.tag !== "string" || typeof row.quantity !== "number" || !Number.isInteger(row.quantity) || row.quantity < 0)) {
    throw new Error("malformed community view-model");
  }
  return {
    version: "community.v1",
    rooms: rooms as CommunityRoom[],
    discussions: discussions.map((row) => {
      const item = row as Record<string, unknown>;
      return { id: item.id as number, title: item.title as string, groupId: item.groupId as number };
    }),
    news: news.map((row) => {
      const item = row as Record<string, unknown>;
      return { id: item.id as number, title: item.title as string, summary: item.summary as string, headerImage: item.headerImage as string, date: item.date as string };
    }),
    tags: tags as CommunityTag[]
  };
}

export const communityFixture: CommunityViewModel = {
  version: "community.v1",
  rooms: [{ id: 1, name: "Retro Lounge", description: "A synthetic public room.", owner: "community" }],
  discussions: [{ id: 1, title: "Welcome discussion", groupId: 1 }],
  news: [{ id: 1, title: "Community update", summary: "A synthetic update.", headerImage: "", date: "2026-01-01" }],
  tags: [{ tag: "retro", quantity: 1 }]
};

export const emptyCommunityFixture: CommunityViewModel = { version: "community.v1", rooms: [], discussions: [], news: [], tags: [] };