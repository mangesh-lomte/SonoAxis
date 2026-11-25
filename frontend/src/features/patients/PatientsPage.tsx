import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Search,
  UserPlus,
  Edit2,
  Trash2,
  FileText,
  AlertCircle,
  X,
  AlertTriangle
} from 'lucide-react';
import { api } from '../../services/api';
import type { Patient, PatientCreate } from '../../types';

export const PatientsPage: React.FC = () => {
  const navigate = useNavigate();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingPatient, setEditingPatient] = useState<Patient | null>(null);
  const [formData, setFormData] = useState<PatientCreate>({
    patient_id: '',
    full_name: '',
    gender: 'Male',
    age_years: undefined,
    referral_doctor: '',
    notes: '',
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteForce, setDeleteForce] = useState<boolean>(false);

  const loadPatients = async (query?: string) => {
    try {
      setLoading(true);
      const data = await api.getPatients(query);
      setPatients(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch patients');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPatients();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadPatients(searchQuery);
  };

  const openCreateModal = () => {
    setEditingPatient(null);
    setFormData({
      patient_id: `PT-${Math.floor(10000 + Math.random() * 90000)}`,
      full_name: '',
      gender: 'Male',
      age_years: undefined,
      referral_doctor: '',
      notes: '',
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (p: Patient) => {
    setEditingPatient(p);
    setFormData({
      patient_id: p.patient_id,
      full_name: p.full_name,
      gender: p.gender || 'Male',
      age_years: p.age_years ?? undefined,
      referral_doctor: p.referral_doctor || '',
      notes: p.notes || '',
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.full_name.trim() || !formData.patient_id.trim()) {
      setFormError('Patient ID and Full Name are required.');
      return;
    }

    try {
      setSaving(true);
      setFormError(null);
      if (editingPatient) {
        await api.updatePatient(editingPatient.id, formData);
      } else {
        await api.createPatient(formData);
      }
      setIsModalOpen(false);
      await loadPatients(searchQuery);
    } catch (err: any) {
      setFormError(err.message || 'Failed to save patient record');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deletePatient(id, deleteForce);
      setDeletingId(null);
      setDeleteForce(false);
      await loadPatients(searchQuery);
    } catch (err: any) {
      if (err.status === 409) {
        alert('This patient has existing reports. Check "Force delete" to delete patient and all linked reports.');
        setDeleteForce(true);
      } else {
        alert(err.message || 'Failed to delete patient');
      }
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Patient Directory</h2>
          <p className="text-xs text-slate-500 mt-0.5">Manage registered clinical patients and ultrasound histories</p>
        </div>
        <button
          onClick={openCreateModal}
          className="flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs rounded-lg shadow-xs transition cursor-pointer"
        >
          <UserPlus className="w-3.5 h-3.5" />
          <span>Register Patient</span>
        </button>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by patient name or MRN..."
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

      {/* Patients Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-500">Loading patients directory...</div>
        ) : error ? (
          <div className="py-12 text-center text-xs text-red-600 flex items-center justify-center gap-2">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        ) : !patients.length ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            <Users className="w-8 h-8 mx-auto mb-2 opacity-40 text-slate-400" />
            No patient records found. Click "Register Patient" to add one.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Patient ID / MRN</th>
                  <th className="py-3 px-4">Full Name</th>
                  <th className="py-3 px-4">Gender / Age</th>
                  <th className="py-3 px-4">Referral Doctor</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {patients.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      <div className="flex items-center gap-1.5">
                        <span>{p.patient_id}</span>
                        {(p.patient_id.startsWith('MRN-2026-104') ||
                          p.full_name.includes('[Demo]') ||
                          (p.notes || '').includes('Fictional')) && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 font-sans font-semibold uppercase tracking-wider">
                            Demo
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900">{p.full_name}</td>
                    <td className="py-3 px-4 text-slate-600">
                      {p.gender} {p.age_years ? `• ${p.age_years} yrs` : ''}
                    </td>
                    <td className="py-3 px-4 text-slate-600">{p.referral_doctor || '—'}</td>
                    <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                      <button
                        onClick={() => navigate(`/reports/new?patient_id=${p.id}`)}
                        title="New Report for this patient"
                        className="p-1.5 text-teal-600 hover:bg-teal-50 rounded transition cursor-pointer"
                      >
                        <FileText className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => openEditModal(p)}
                        title="Edit Patient"
                        className="p-1.5 text-slate-600 hover:bg-slate-100 rounded transition cursor-pointer"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setDeletingId(p.id)}
                        title="Delete Patient"
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

      {/* Patient Create / Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50">
              <h3 className="font-bold text-slate-900 text-sm">
                {editingPatient ? 'Edit Patient Profile' : 'Register New Patient'}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleFormSubmit} className="p-5 space-y-3.5">
              {formError && (
                <div className="p-2.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Patient ID / MRN *
                </label>
                <input
                  type="text"
                  required
                  value={formData.patient_id}
                  onChange={(e) => setFormData({ ...formData, patient_id: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                  placeholder="e.g. MRN-10024"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Full Name *</label>
                <input
                  type="text"
                  required
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                  placeholder="e.g. Ramesh Chandra"
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Gender *</label>
                  <select
                    value={formData.gender}
                    onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                    className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Age (Years)</label>
                  <input
                    type="number"
                    min="0"
                    max="125"
                    value={formData.age_years ?? ''}
                    onChange={(e) =>
                      setFormData({ ...formData, age_years: e.target.value ? parseInt(e.target.value) : undefined })
                    }
                    className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                    placeholder="e.g. 45"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Referral Doctor
                </label>
                <input
                  type="text"
                  value={formData.referral_doctor || ''}
                  onChange={(e) => setFormData({ ...formData, referral_doctor: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                  placeholder="e.g. Dr. Sameer Joshi"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3.5 py-1.5 border border-slate-200 text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg disabled:opacity-50 cursor-pointer shadow-xs"
                >
                  {saving ? 'Saving...' : editingPatient ? 'Update Patient' : 'Register Patient'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingId && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-5 space-y-3.5 border border-slate-200">
            <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="text-center">
              <h4 className="font-bold text-slate-900 text-sm">Delete Patient Record?</h4>
              <p className="text-xs text-slate-500 mt-1">This action cannot be undone.</p>
            </div>
            {deleteForce && (
              <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                Patient has associated ultrasound studies. Deleting will cascade and permanently remove all linked
                reports.
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setDeletingId(null);
                  setDeleteForce(false);
                }}
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
