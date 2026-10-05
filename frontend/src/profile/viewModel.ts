export type ProfileViewModel = {
  version: "profile.v1";
  profile: {
    id: number;
    username: string;
    motto: string;
    look: string;
    gender: "M" | "F";
    accountCreated: string;
  };
  tab: 1 | 2 | 3 | 4 | 5;
};

function normalizeProfileTab(value: unknown): ProfileViewModel["tab"] {
  return typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= 5
    ? value as ProfileViewModel["tab"]
    : 1;
}

export function acceptProfileViewModel(value: unknown): ProfileViewModel {
  if (!value || typeof value !== "object" || (value as { version?: unknown }).version !== "profile.v1") {
    throw new Error("unsupported profile view-model version");
  }
  const candidate = value as { profile?: unknown; tab?: unknown };
  if (!candidate.profile || typeof candidate.profile !== "object") {
    throw new Error("malformed profile view-model");
  }
  const profile = candidate.profile as Partial<ProfileViewModel["profile"]>;
  if (typeof profile.id !== "number" || !Number.isInteger(profile.id) || profile.id <= 0 ||
      typeof profile.username !== "string" || typeof profile.motto !== "string" ||
      typeof profile.look !== "string" || (profile.gender !== "M" && profile.gender !== "F") ||
      typeof profile.accountCreated !== "string") {
    throw new Error("malformed profile view-model");
  }
  return {
    version: "profile.v1",
    profile: {
      id: profile.id,
      username: profile.username,
      motto: profile.motto,
      look: profile.look,
      gender: profile.gender,
      accountCreated: profile.accountCreated
    },
    tab: normalizeProfileTab(candidate.tab)
  };
}
