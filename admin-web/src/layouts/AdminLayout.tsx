import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutGrid, Vault, ClipboardList, Users, UserPlus, Building2, ShieldCheck, BarChart3, Settings, LogOut, Bell,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutGrid, end: true },
  { to: "/vault", label: "Locker Vault", icon: Vault },
  { to: "/requests", label: "Requests", icon: ClipboardList },
  { to: "/customers", label: "Customers", icon: Users },
  { to: "/enrollment", label: "Face Enrollment", icon: UserPlus },
  { to: "/compliance", label: "Compliance & Audit", icon: ShieldCheck },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
];


export function AdminLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex bg-bg">
      <aside className="w-60 shrink-0 bg-primary text-slate-200 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-700">
          <div className="text-white font-semibold text-sm tracking-wide">DIGITAL LOCKER</div>
          <div className="text-slate-400 text-xs">Bank Admin Portal</div>
        </div>
        <nav className="flex-1 py-3 px-2 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive ? "bg-slate-800 text-white" : "hover:bg-slate-800/60 text-slate-300"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-4 border-t border-slate-700">
          <button
            onClick={logout}
            className="flex items-center gap-2 text-sm text-slate-300 hover:text-white px-3 py-2 w-full"
          >
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-6">
          <input
            type="text"
            placeholder="Search lockers, requests, customers..."
            className="w-96 max-w-full text-sm border border-border rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <div className="flex items-center gap-4">
            <button className="text-slate-500 hover:text-primary"><Bell size={18} /></button>
            <div className="text-sm text-right leading-tight">
              <div className="font-medium text-primary">{user?.full_name}</div>
              <div className="text-xs text-slate-500">{user?.role?.replace("_", " ")}</div>
            </div>
            <div className="w-8 h-8 rounded-full bg-primary text-white text-xs flex items-center justify-center font-semibold">
              {user?.full_name?.slice(0, 2).toUpperCase()}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
