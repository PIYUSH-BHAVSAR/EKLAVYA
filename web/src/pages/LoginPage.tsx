import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";

export default function LoginPage() {
  const { setAuth } = useAuth();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.login(username, password);
      setAuth(res.token, res.role, res.username);
      nav(res.role === "admin" ? "/admin/overview" : "/app/chat", { replace: true });
    } catch {
      setError("Invalid username or password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-light flex flex-col">
      {/* Saffron strip */}
      <div className="h-1 bg-saffron" />
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          {/* Brand */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-navy">EKLAVYA</h1>
            <p className="text-sm text-gray-500 mt-1">Government Resolution Assistant</p>
            <p className="text-xs text-gray-400 mt-0.5">एकलव्य — शासन निर्णय सहाय्यक</p>
          </div>

          {/* Card */}
          <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 space-y-5">
            <h2 className="text-lg font-semibold text-ink">Sign in</h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy/30"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="citizen or admin"
                autoComplete="username"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy/30"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <p className="text-red-500 text-sm">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-navy text-white rounded-lg py-2.5 text-sm font-semibold hover:bg-navy/90 disabled:opacity-50 transition"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>

            <div className="text-xs text-gray-400 text-center space-y-0.5">
              <p>Demo accounts: <code>citizen / citizen123</code></p>
              <p className="ml-16"><code>admin / admin123</code></p>
            </div>
          </form>

          <p className="text-center text-xs text-gray-400 mt-6">
            Demo prototype — not an official government service.
          </p>
        </div>
      </div>
    </div>
  );
}
