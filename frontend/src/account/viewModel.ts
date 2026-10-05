export type AccountWidget = {
  name: string;
  value: string;
};

export type AccountViewModel = {
  version: "account.v1";
  profile: {
    id: number;
    username: string;
    motto: string;
    look: string;
    gender: "M" | "F";
    accountCreated: string;
  };
  status: string;
  widgets: AccountWidget[];
};

export function acceptAccountViewModel(value: unknown): AccountViewModel {
  if (!value || typeof value !== "object" || (value as { version?: unknown }).version !== "account.v1") {
    throw new Error("unsupported account view-model version");
  }
  const candidate = value as { profile?: unknown; status?: unknown; widgets?: unknown };
  if (!candidate.profile || typeof candidate.profile !== "object" || typeof candidate.status !== "string") {
    throw new Error("malformed account view-model");
  }
  const input = candidate.profile as Partial<AccountViewModel["profile"]>;
  if (typeof input.id !== "number" || !Number.isInteger(input.id) || input.id <= 0 ||
      typeof input.username !== "string" || typeof input.motto !== "string" ||
      typeof input.look !== "string" || (input.gender !== "M" && input.gender !== "F") ||
      typeof input.accountCreated !== "string") {
    throw new Error("malformed account view-model");
  }
  const widgets = candidate.widgets === undefined ? [] : candidate.widgets;
  if (!Array.isArray(widgets) || widgets.some((widget) => !widget || typeof widget !== "object" ||
      typeof (widget as { name?: unknown }).name !== "string" ||
      typeof (widget as { value?: unknown }).value !== "string")) {
    throw new Error("malformed account view-model");
  }
  return {
    version: "account.v1",
    profile: {
      id: input.id,
      username: input.username,
      motto: input.motto,
      look: input.look,
      gender: input.gender,
      accountCreated: input.accountCreated
    },
    status: candidate.status,
    widgets: widgets.map((widget) => ({
      name: (widget as AccountWidget).name,
      value: (widget as AccountWidget).value
    }))
  };
}
