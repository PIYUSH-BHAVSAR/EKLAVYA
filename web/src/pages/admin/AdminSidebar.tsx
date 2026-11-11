import { NavLink, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, GitBranch, FileText, BookOpen,
  ClipboardCheck, Globe, MessageSquare, BarChart2,
  ShieldCheck, ScrollText, Settings, LogOut, Bell,
} from "lucide-react";
import { useAuth } from "../../AuthContext";
import { api, Notification } from "../../api";
import LlmStatusChip from "../../components/LlmStatusChip";

const GROUPS = [
  {
    label: "Monitor",
    items: [
      { to: "/admin/overview",   icon: LayoutDashboard, label: "Overview" },
      { to: "/admin/pipeline",   icon: GitBranch,       label: "Pipeline" },
    ],
  },
  {
    label: "Content",
    items: [
      { to: "/admin/documents",  icon: FileText,        label: "Documents" },
      { to: "/admin/rules",      icon: BookOpen,        label: "Rules" },
      { to: "/admin/review",     icon: ClipboardCheck,  label: "Review Queue" },
    ],
  },
  {
    label: "Operate",
    items: [
      { to: "/admin/sources",    icon: Globe,           label: "Sources" },
      { to: "/admin/questions",  icon: MessageSquare,   label: "Questions" },
      { to: "/admin/evaluation", icon: BarChart2,       label: "Evaluation" },
    ],
  },
  {
    label: "Govern",
    items: [
      { to: "/admin/guardrails", icon: ShieldCheck,     label: "Guardrails" },
      { to: "/admin/audit",      icon: ScrollText,      label: "Audit Log" },
      { to: "/admin/settings",   icon: Settings,        label: "Settings" },
    ],
  },
];

export default function AdminSidebar() {
  const { clearAuth, username } = useAuth();
  const nav = useNavigate();
  const [notifs, setNotifs] = useState<Notification[]>([]);

  useEffect(() => {
    const load = () => api.notifications().then(setNotifs).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const unread = notifs.filter(n => !n.read).length;

  function handleLogout() {
    api.logout().catch(() => {});
    clearAuth();
    nav("/login");
  }

  return (
    <aside className="w-56 bg-navy flex flex-col shrink-0 overflow-hidden">
      {/* Brand + top bar */}
      <div className="px-4 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-white font-bold text-base leading-none">EKLAVYA</h1>
            <p className="text-white/40 text-xs mt-0.5">Admin · {username}</p>
          </div>
          <button
            onClick={() => nav("/admin/overview")}
            className="relative text-white/60 hover:text-white transition"
            aria-label="Notifications"
          >
            <Bell size={18} />
            {unread > 0 && (
              <span className="absolute -top-1 -right-1 bg-saffron text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </button>
        </div>
        <p className="text-white/30 text-xs mt-1">
          शबरी महामंडळ · Pilot: Nashik
        </p>
        {/* LLM status chip — shows model loaded / loading / offline */}
        <div className="mt-2">
          <LlmStatusChip variant="compact" />
        </div>
      </div>

      {/* Nav groups */}
      <nav className="flex-1 overflow-y-auto py-2">
        {GROUPS.map(g => (
          <div key={g.label} className="mb-1">
            <p className="text-white/25 text-[10px] font-semibold uppercase tracking-wider px-4 py-1.5">
              {g.label}
            </p>
            {g.items.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-4 py-2 text-sm transition rounded-none ${
                    isActive
                      ? "bg-white/10 text-white font-medium border-r-2 border-saffron"
                      : "text-white/60 hover:text-white hover:bg-white/5"
                  }`
                }
              >
                <Icon size={15} />
                {label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-white/10 px-4 py-3">
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-white/50 hover:text-white text-sm transition w-full"
        >
          <LogOut size={14} />
          Log out
        </button>
      </div>
    </aside>
  );
}
