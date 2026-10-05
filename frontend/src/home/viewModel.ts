export type HomeRecord = {
  ownerId: number;
  username: string;
  showHome: boolean;
  publicContent: string;
};

export type HomeViewer = { ownerId?: number };

export type HomeViewModel = {
  version: "home.v1";
  ownerId: number;
  username: string;
  publicContent: string;
};

export function presentHome(record: HomeRecord, viewer: HomeViewer = {}): HomeViewModel {
  if (!Number.isInteger(record.ownerId) || record.ownerId <= 0 || record.username.trim() === "") {
    throw new Error("home owner not found");
  }
  const isOwner = viewer.ownerId === record.ownerId;
  if (!record.showHome && !isOwner) {
    throw new Error("unsupported home state");
  }
  const model: HomeViewModel = {
    version: "home.v1",
    ownerId: record.ownerId,
    username: record.username,
    publicContent: record.publicContent
  };
  return model;
}

export function acceptHomeViewModel(value: unknown): HomeViewModel {
  if (!value || typeof value !== "object" || (value as { version?: unknown }).version !== "home.v1") {
    throw new Error("unsupported view-model version");
  }
  const model = value as HomeViewModel;
  if (!Number.isInteger(model.ownerId) || model.ownerId <= 0 || typeof model.username !== "string" ||
      typeof model.publicContent !== "string") {
    throw new Error("malformed home view-model");
  }
  return model;
}
