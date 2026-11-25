import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  FilePlus,
  Users,
  FileText,
  Layers,
  Settings as SettingsIcon,
  Cpu,
  AlertCircle,
  Activity,
  LogOut,
  UserCheck,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import type { EngineStatus } from '../types';

export const AppLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const [eng] = await Promise.all([api.getEngineStatus(), api.getHealth()]);
        setEngineStatus(eng);
        setBackendOnline(true);
      } catch {
        setBackendOnline(false);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSignOut = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const getInitials = (name?: string) => {
    if (!name) return 'DR';
    const parts = name.replace(/^Dr\.?\s+/i, '').trim().split(/\s+/);
    return ((parts[0]?.[0] || 'D') + (parts[1]?.[0] || 'R')).toUpperCase();
  };

  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/reports/new', label: 'New Report', icon: FilePlus, highlight: true },
    { to: '/patients', label: 'Patients', icon: Users },
    { to: '/reports', label: 'Reports', icon: FileText },
    { to: '/templates', label: 'Templates', icon: Layers },
    { to: '/settings', label: 'Settings', icon: SettingsIcon },
  ];

  const getPageTitle = () => {
    const p = location.pathname;
    if (p === '/') return 'Dashboard';
    if (p.startsWith('/reports/new')) return 'New Report Setup';
    if (p.startsWith('/reports/') && p !== '/reports') return 'Ultrasound Reporting Workspace';
    if (p.startsWith('/reports')) return 'Reports Registry';
    if (p.startsWith('/patients')) return 'Patients Directory';
    if (p.startsWith('/templates')) return 'Institutional Templates';
    if (p.startsWith('/settings')) return 'Profile & Administration';
    return 'Dashboard';
  };

  return (
    <div className="flex h-screen bg-[#F8FAFC] overflow-hidden text-slate-800 font-sans">
      {/* SIDEBAR */}
      <aside className="w-64 bg-[#0F172A] flex flex-col justify-between text-slate-200 border-r border-slate-800/80 shadow-md flex-shrink-0 z-20">
        <div>
          {/* Brand Header */}
          <div className="px-5 py-4 border-b border-slate-800/80 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center shadow-xs text-white font-bold text-lg tracking-tight">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-bold text-base text-white tracking-tight leading-tight flex items-center gap-1">
                Sono<span className="text-teal-400">Axis</span>
              </div>
              <div className="text-[10px] text-slate-400 font-medium tracking-normal">
                Ultrasound Reporting Suite
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Clinical Workspace
            </div>
            {navItems.map(item => {
              const Icon = item.icon;
              const isItemActive = (() => {
                const p = location.pathname;
                if (item.to === '/') return p === '/';
                if (item.to === '/reports/new') return p === '/reports/new';
                if (item.to === '/reports') return p === '/reports' || (p.startsWith('/reports/') && p !== '/reports/new');
                return p.startsWith(item.to);
              })();
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/' || item.to === '/reports'}
                  aria-current={isItemActive ? 'page' : undefined}
                  className={() =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 ${isItemActive
                      ? 'bg-[#1E293B] text-white shadow-xs border-l-2 border-teal-500 pl-2.5'
                      : 'text-slate-300 hover:bg-slate-800/70 hover:text-white'
                    } ${item.highlight && !isItemActive ? 'text-teal-300/90 hover:text-teal-200' : ''}`
                  }
                >
                  <Icon className="w-4 h-4 flex-shrink-0 text-slate-300" />
                  <span>{item.label}</span>
                  {item.highlight && (
                    <span className="ml-auto text-[10px] font-semibold bg-teal-900/60 text-teal-300 border border-teal-700/50 px-1.5 py-0.5 rounded">
                      +
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Authenticated Doctor Profile Card */}
        <div className="p-3.5 border-t border-slate-800/80 space-y-2.5">
          {user && (
            <div className="p-2.5 rounded-lg bg-[#020617] border border-slate-800 space-y-2">
              <div
                onClick={() => navigate('/settings')}
                className="flex items-center gap-2.5 cursor-pointer group"
                title="View doctor profile & account settings"
              >
                <div className="w-8 h-8 rounded-lg bg-teal-700/80 border border-teal-500/40 text-white font-bold text-xs flex items-center justify-center shrink-0">
                  {getInitials(user.full_name)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold text-white truncate group-hover:text-teal-300 transition">
                    {user.display_name}
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide ${user.role === 'Administrator'
                        ? 'bg-indigo-950/90 text-indigo-300 border border-indigo-700/50'
                        : 'bg-emerald-950/90 text-emerald-300 border border-emerald-700/50'
                        }`}
                    >
                      {user.role}
                    </span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleSignOut}
                className="w-full py-1.5 px-2.5 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-700/70 text-[11px] font-semibold text-slate-300 hover:text-white flex items-center justify-center gap-1.5 transition cursor-pointer"
              >
                <LogOut className="w-3 h-3" />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-14 bg-white border-b border-slate-200/90 px-6 flex items-center justify-between shadow-xs flex-shrink-0 z-10">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400 font-medium">SonoAxis</span>
            <span className="text-slate-300 text-xs">/</span>
            <h1 className="text-sm font-bold text-slate-900 tracking-tight">{getPageTitle()}</h1>
          </div>

          <div className="flex items-center gap-3">
            {backendOnline ? (
              <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-md text-[11px] text-slate-600">
                <Cpu className="w-3.5 h-3.5 text-teal-600" />
                <span>
                  Whisper: <strong className="text-slate-800 font-semibold">{engineStatus?.active_model || 'small.en'}</strong>
                </span>
                <span className="text-slate-300">|</span>
                <span className="flex items-center gap-1 text-emerald-600 font-semibold text-[11px]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block"></span>
                  Online
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-red-50 border border-red-200 rounded-md text-xs text-red-700 font-medium">
                <AlertCircle className="w-3.5 h-3.5" />
                Service Unavailable
              </div>
            )}

            {user && (
              <button
                type="button"
                onClick={() => navigate('/settings')}
                className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-md text-[11px] text-slate-700 transition cursor-pointer"
                title={user.designation || user.role}
              >
                <UserCheck className="w-3.5 h-3.5 text-teal-600" />
                <span className="font-semibold text-slate-900">{user.full_name}</span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-600">{user.role}</span>
              </button>
            )}
          </div>
        </header>

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#F8FAFC]">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
