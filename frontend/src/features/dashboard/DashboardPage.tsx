import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FilePlus,
  Users,
  FileText,
  Clock,
  CheckCircle2,
  ArrowRight,
  Layers,
  Activity,
  HeartPulse,
  Sparkles,
  FileClock,
} from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import type { DashboardStats, ReportListItem } from '../../types';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const data = await api.getDashboardStats();
        setStats(data);
      } catch (err: any) {
        console.error('Failed to load dashboard metrics', err);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header & Clinical Operations Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-1">
        <div>
          <div className="text-[10px] font-bold text-teal-700 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <span className="w-1.5 h-1.5 rounded-full bg-teal-500 inline-block"></span>
            {user?.department || 'Department of Radiology & Imaging'}
          </div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            {user ? `Welcome, ${user.full_name}` : 'SonoAxis Clinical Workspace'}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {user
              ? `${user.designation || user.role} · Structured Ultrasound & Doppler Reporting`
              : 'Structured Ultrasound & Doppler Reporting'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/reports/new')}
            className="flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg shadow-xs transition cursor-pointer"
          >
            <FilePlus className="w-3.5 h-3.5" />
            <span>New Report</span>
          </button>
        </div>
      </div>

      {/* Metric Cards Grid (4 Clinical KPIs) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div
          onClick={() => navigate('/reports')}
          className="p-4 bg-white border border-slate-200 hover:border-teal-400 rounded-xl shadow-xs flex items-center justify-between cursor-pointer transition"
        >
          <div>
            <div className="text-xs font-semibold text-slate-500">Total Studies</div>
            <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
              {loading ? '—' : stats?.total_reports ?? 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">
              {loading ? 'Loading...' : `${stats?.today_reports ?? 0} recorded today`}
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-teal-50 border border-teal-100 text-teal-700 flex items-center justify-center">
            <FileText className="w-5 h-5 text-teal-600" />
          </div>
        </div>

        <div
          onClick={() => navigate('/reports')}
          className="p-4 bg-white border border-slate-200 hover:border-amber-400 rounded-xl shadow-xs flex items-center justify-between cursor-pointer transition"
        >
          <div>
            <div className="text-xs font-semibold text-amber-700">Pending Drafts</div>
            <div className="text-2xl font-bold text-amber-900 mt-1 font-mono">
              {loading ? '—' : stats?.draft_reports ?? 0}
            </div>
            <div className="text-[11px] text-amber-700/80 mt-0.5 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>Awaiting radiologist sign-off</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 flex items-center justify-center">
            <FileClock className="w-5 h-5 text-amber-600" />
          </div>
        </div>

        <div
          onClick={() => navigate('/reports')}
          className="p-4 bg-white border border-slate-200 hover:border-emerald-400 rounded-xl shadow-xs flex items-center justify-between cursor-pointer transition"
        >
          <div>
            <div className="text-xs font-semibold text-emerald-700">Reviewed &amp; Verified</div>
            <div className="text-2xl font-bold text-emerald-900 mt-1 font-mono">
              {loading ? '—' : stats?.reviewed_reports ?? 0}
            </div>
            <div className="text-[11px] text-emerald-700/80 mt-0.5 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              <span>Clinically finalized</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          </div>
        </div>

        <div
          onClick={() => navigate('/patients')}
          className="p-4 bg-white border border-slate-200 hover:border-blue-400 rounded-xl shadow-xs flex items-center justify-between cursor-pointer transition"
        >
          <div>
            <div className="text-xs font-semibold text-slate-500">Registered Patients</div>
            <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
              {loading ? '—' : stats?.total_patients ?? 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Active patient directory</div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-blue-50 border border-blue-100 text-blue-700 flex items-center justify-center">
            <Users className="w-5 h-5 text-blue-600" />
          </div>
        </div>
      </div>

      {/* Examination Suites Launchers */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Examination Protocols
          </div>
          <span className="text-[11px] text-slate-500">Select protocol to initiate study</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div
            onClick={() => navigate('/reports/new?category=abdomen_pelvis')}
            className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-teal-400 hover:shadow-sm cursor-pointer transition flex items-start gap-3"
          >
            <div className="w-9 h-9 rounded-lg bg-teal-50 border border-teal-200 text-teal-700 flex items-center justify-center shrink-0">
              <Layers className="w-4 h-4 text-teal-600" />
            </div>
            <div>
              <div className="font-bold text-xs text-slate-900">Abdomen &amp; Pelvis</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Male &amp; Female canonical organs</div>
            </div>
          </div>

          <div
            onClick={() => navigate('/reports/new?category=venous_doppler')}
            className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-teal-400 hover:shadow-sm cursor-pointer transition flex items-start gap-3"
          >
            <div className="w-9 h-9 rounded-lg bg-teal-50 border border-teal-200 text-teal-700 flex items-center justify-center shrink-0">
              <Activity className="w-4 h-4 text-teal-600" />
            </div>
            <div>
              <div className="font-bold text-xs text-slate-900">Venous Doppler</div>
              <div className="text-[11px] text-slate-500 mt-0.5">DVT, reflux &amp; perforators</div>
            </div>
          </div>

          <div
            onClick={() => navigate('/reports/new?category=arterial_doppler')}
            className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-teal-400 hover:shadow-sm cursor-pointer transition flex items-start gap-3"
          >
            <div className="w-9 h-9 rounded-lg bg-teal-50 border border-teal-200 text-teal-700 flex items-center justify-center shrink-0">
              <HeartPulse className="w-4 h-4 text-teal-600" />
            </div>
            <div>
              <div className="font-bold text-xs text-slate-900">Arterial Doppler</div>
              <div className="text-[11px] text-slate-500 mt-0.5">PSV table &amp; waveform hemodynamics</div>
            </div>
          </div>

          <div
            onClick={() => navigate('/reports/new?category=arteriovenous_doppler')}
            className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-teal-400 hover:shadow-sm cursor-pointer transition flex items-start gap-3"
          >
            <div className="w-9 h-9 rounded-lg bg-teal-50 border border-teal-200 text-teal-700 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-teal-600" />
            </div>
            <div>
              <div className="font-bold text-xs text-slate-900">Combined Doppler</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Arteriovenous bilateral evaluation</div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Reports Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs p-4">
        <div className="flex items-center justify-between mb-3 pb-2.5 border-b border-slate-100">
          <div className="font-bold text-slate-900 text-xs uppercase tracking-wider flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-teal-600" />
            Recent Ultrasound Studies
          </div>
          <button
            onClick={() => navigate('/reports')}
            className="text-xs font-semibold text-teal-700 hover:text-teal-800 flex items-center gap-1 cursor-pointer"
          >
            View all reports <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        {loading ? (
          <div className="py-8 text-center text-xs text-slate-500">Loading recent studies...</div>
        ) : !stats?.recent_reports?.length ? (
          <div className="py-10 text-center text-slate-400 text-xs">
            <FileText className="w-7 h-7 mx-auto mb-1.5 opacity-40 text-slate-400" />
            No clinical reports recorded yet. Click "New Report" to begin.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {stats.recent_reports.map((r: ReportListItem) => (
              <div
                key={r.id}
                onClick={() => navigate(`/reports/${r.id}`)}
                className="py-2.5 px-2 flex items-center justify-between hover:bg-slate-50 rounded-lg cursor-pointer transition"
              >
                <div className="min-w-0 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900 text-xs font-mono">
                      {r.report_number || r.id.slice(0, 8)}
                    </span>
                    <span className="text-xs text-slate-700 font-semibold truncate max-w-xs">
                      {r.patient_name || 'Unlinked Patient'}
                    </span>
                    {((r.patient_name || '').includes('[Demo]') ||
                      (r.report_number || '').startsWith('RPT-2026-10')) && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 font-semibold uppercase tracking-wider">
                        Demo
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
                    <span className="truncate max-w-xs">{r.template_name || r.template_id}</span>
                    <span>·</span>
                    <span>{r.report_date}</span>
                    <span>·</span>
                    <span className="font-mono">Rev #{r.revision_number}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2.5">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-bold tracking-wide uppercase ${
                      r.status === 'REVIEWED'
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                        : 'bg-amber-100 text-amber-800 border border-amber-200'
                    }`}
                  >
                    {r.status}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
