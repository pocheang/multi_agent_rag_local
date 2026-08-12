export type KnownUserRole = "admin" | "analyst" | "viewer";

export type UserIdentity = {
  user_id: string;
  username: string;
  display_name?: string | null;
  role: string;
  status: string;
};

export function toKnownUserRole(role: unknown): KnownUserRole {
  if (typeof role !== "string") return "viewer";

  const normalizedRole = role.toLowerCase();
  if (normalizedRole === "admin" || normalizedRole === "analyst" || normalizedRole === "viewer") {
    return normalizedRole;
  }

  return "viewer";
}
