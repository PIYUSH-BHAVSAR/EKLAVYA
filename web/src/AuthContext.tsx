import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { Lang } from "./i18n";

interface AuthState {
  token: string | null;
  role: "citizen" | "admin" | null;
  username: string | null;
  lang: Lang;
  setLang: (l: Lang) => void;
  setAuth: (token: string, role: string, username: string) => void;
  clearAuth: () => void;
}

const AuthContext = createContext<AuthState>({
  token: null, role: null, username: null, lang: "en",
  setLang: () => {}, setAuth: () => {}, clearAuth: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("eklavya_token")
  );
  const [role, setRole] = useState<"citizen" | "admin" | null>(
    () => localStorage.getItem("eklavya_role") as "citizen" | "admin" | null
  );
  const [username, setUsername] = useState<string | null>(
    () => localStorage.getItem("eklavya_user")
  );
  const [lang, setLang] = useState<Lang>("en");

  function setAuth(t: string, r: string, u: string) {
    localStorage.setItem("eklavya_token", t);
    localStorage.setItem("eklavya_role", r);
    localStorage.setItem("eklavya_user", u);
    setToken(t);
    setRole(r as "citizen" | "admin");
    setUsername(u);
  }

  function clearAuth() {
    localStorage.removeItem("eklavya_token");
    localStorage.removeItem("eklavya_role");
    localStorage.removeItem("eklavya_user");
    setToken(null);
    setRole(null);
    setUsername(null);
  }

  return (
    <AuthContext.Provider value={{ token, role, username, lang, setLang, setAuth, clearAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
