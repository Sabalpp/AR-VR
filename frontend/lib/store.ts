import { create } from "zustand";
type User = { id: string; email: string; role: string };
export const useSession = create<{
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
}>((set) => ({
  token: null,
  user: null,
  setAuth: (token, user) => {
    sessionStorage.setItem("reach-auth", JSON.stringify({ token, user }));
    set({ token, user });
  },
  logout: () => {
    sessionStorage.removeItem("reach-auth");
    set({ token: null, user: null });
  },
}));
export function restoreAuth() {
  try {
    const raw = sessionStorage.getItem("reach-auth");
    if (raw) useSession.setState(JSON.parse(raw));
  } catch {
    sessionStorage.removeItem("reach-auth");
  }
}
