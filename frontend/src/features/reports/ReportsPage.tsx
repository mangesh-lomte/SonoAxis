import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  Filter,
  FilePlus,
  Download,
  Trash2,
  AlertTriangle,
  AlertCircle
} from 'lucide-react';
import { api } from '../../services/api';
import type { ReportListItem } from '../../types';

export const ReportsPage: React.FC = () => {
  const navigate = useNavigate();
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [templateFilter, setTemplateFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Delete modal
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadReports = async () => {
    try {
      setLoading(true);
      const data = await api.getReports({
        status: statusFilter || undefined,
        template_id: templateFilter || undefined,
        query: searchQuery || undefined,
      });
      setReports(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load clinical reports');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, [statusFilter, templateFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadReports();
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteReport(id);
      setDeletingId(null);
      await loadReports();
    } catch (err: any) {
      alert(err.message || 'Failed to delete report');
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Clinical Reports Registry</h2>
          <p className="text-xs text-slate-500 mt-0.5">Comprehensive audit trail of drafted and reviewed ultrasound studies</p>
        </div>
        <button
          onClick={() => navigate('/reports/new')}
          className="flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs rounded-lg shadow-xs transition cursor-pointer"
        >
          <FilePlus className="w-3.5 h-3.5" />
          <span>New Report</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs flex flex-wrap gap-3 items-center justify-between">
        <form onSubmit={handleSearchSubmit} className="flex gap-2 flex-1 min-w-[260px] max-w-md">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by report # or patient name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-teal-500"
            />
          </div>
          <button
            type="submit"
            className="px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 cursor-pointer"
          >
            Search
          </button>
        </form>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1 border border-slate-200 rounded-md text-xs text-slate-800 bg-white focus:outline-none focus:border-teal-500"
            >
              <option value="">All Statuses</option>
              <option value="DRAFT">DRAFT</option>
              <option value="REVIEWED">REVIEWED</option>
            </select>
          </div>

          {/* Template Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span>Template:</span>
            <select
              value={templateFilter}
              onChange={(e) => setTemplateFilter(e.target.value)}
              className="px-2.5 py-1 border border-slate-200 rounded-md text-xs text-slate-800 bg-white focus:outline-none focus:border-teal-500"
            >
              <option value="">All Templates</option>
              <option value="usg-abdomen-pelvis-male">Male Abdomen & Pelvis</option>
              <option value="usg-abdomen-pelvis-female">Female Abdomen & Pelvis</option>
            </select>
          </div>
        </div>
      </div>

      {/* Reports Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-500">Loading reports registry...</div>
        ) : error ? (
          <div className="py-12 text-center text-xs text-red-600 flex items-center justify-center gap-2">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        ) : !reports.length ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-40 text-slate-400" />
            No ultrasound reports match your active filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Report Number</th>
                  <th className="py-3 px-4">Patient Name</th>
                  <th className="py-3 px-4">Protocol</th>
                  <th className="py-3 px-4">Study Date</th>
                  <th className="py-3 px-4">Rev</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {reports.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      <button
                        onClick={() => navigate(`/reports/${r.id}`)}
                        className="text-teal-700 hover:text-teal-900 hover:underline cursor-pointer text-left font-mono"
                      >
                        {r.report_number || r.id.slice(0, 8)}
                      </button>
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      <div className="flex items-center gap-1.5">
                        <span>{r.patient_name || 'Anonymous'}</span>
                        {((r.patient_name || '').includes('[Demo]') ||
                          (r.report_number || '').startsWith('RPT-2026-10')) && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 font-semibold uppercase tracking-wider">
                            Demo
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-600 text-xs truncate max-w-xs">
                      {r.template_name || r.template_id}
                    </td>
                    <td className="py-3 px-4 text-slate-600 text-xs">{r.report_date}</td>
                    <td className="py-3 px-4 text-slate-500 font-mono text-xs">#{r.revision_number}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold tracking-wide uppercase ${
                          r.status === 'REVIEWED'
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : 'bg-amber-100 text-amber-800 border border-amber-200'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right space-x-1 whitespace-nowrap">
                      <button
                        onClick={() => navigate(`/reports/${r.id}`)}
                        title="Open Reporting Workspace"
                        className="p-1.5 text-teal-600 hover:bg-teal-50 rounded transition cursor-pointer"
                      >
                        <FileText className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => window.open(api.getReportDocxUrl(r.id), '_blank')}
                        title="Download Word DOCX"
                        className="p-1.5 text-slate-600 hover:bg-slate-100 rounded transition cursor-pointer"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setDeletingId(r.id)}
                        title="Delete Report"
                        className="p-1.5 text-red-600 hover:bg-red-50 rounded transition cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deletingId && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-5 space-y-3.5 border border-slate-200">
            <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="text-center">
              <h4 className="font-bold text-slate-900 text-sm">Delete Clinical Report?</h4>
              <p className="text-xs text-slate-500 mt-1">
                Are you sure you want to permanently delete this report and its associated dictation audio?
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setDeletingId(null)}
                className="flex-1 py-1.5 border border-slate-200 text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deletingId)}
                className="flex-1 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg cursor-pointer"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
