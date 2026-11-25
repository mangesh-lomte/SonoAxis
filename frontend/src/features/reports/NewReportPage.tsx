import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Users,
  Calendar,
  Layers,
  ArrowRight,
  AlertCircle,
  UserPlus,
  Check,
  ShieldAlert,
  Activity,
  HeartPulse,
  Clock,
  Sparkles,
  FileSpreadsheet
} from 'lucide-react';
import { api } from '../../services/api';
import type { Patient, PatientCreate, TemplateDef } from '../../types';

interface ExamCategoryOption {
  key: string;
  label: string;
  description: string;
  icon: any;
  defaultLaterality?: string;
}

const EXAM_CATEGORIES: ExamCategoryOption[] = [
  {
    key: 'abdomen_pelvis',
    label: 'Abdomen & Pelvis',
    description: 'Canonical abdominal organs, retroperitoneum, urinary system, and reproductive anatomy.',
    icon: Layers,
    defaultLaterality: 'not_applicable'
  },
  {
    key: 'venous_doppler',
    label: 'Lower Limb Venous Doppler',
    description: 'DVT assessment, compressibility, GSV/SSV incompetence, and repeatable perforator cards.',
    icon: Activity,
    defaultLaterality: 'bilateral'
  },
  {
    key: 'arterial_doppler',
    label: 'Lower Limb Arterial Doppler',
    description: 'Arterial biometry table with PSV values and categorical triphasic/biphasic/monophasic flow patterns.',
    icon: HeartPulse,
    defaultLaterality: 'bilateral'
  },
  {
    key: 'arteriovenous_doppler',
    label: 'Combined Arteriovenous Doppler',
    description: 'Simultaneous arterial hemodynamic analysis and venous incompetence examination.',
    icon: Sparkles,
    defaultLaterality: 'bilateral'
  },
  {
    key: 'custom',
    label: 'Custom / Imported Templates',
    description: 'Clinician-imported Word protocols and personalized reporting layouts.',
    icon: FileSpreadsheet,
    defaultLaterality: 'not_applicable'
  }
];

export const NewReportPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>(
    searchParams.get('patient_id') || ''
  );
  const [templates, setTemplates] = useState<TemplateDef[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState<boolean>(true);

  const [selectedCategory, setSelectedCategory] = useState<string>(
    searchParams.get('category') || 'abdomen_pelvis'
  );
  const [selectedLaterality, setSelectedLaterality] = useState<string>('all');
  const [templateId, setTemplateId] = useState<string>(
    searchParams.get('template') || 'usg-abdomen-pelvis-male'
  );

  const [reportDate, setReportDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [referralDoctor, setReferralDoctor] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Quick Register Patient
  const [showQuickRegister, setShowQuickRegister] = useState<boolean>(false);
  const [quickPatient, setQuickPatient] = useState<PatientCreate>({
    patient_id: `PT-${Math.floor(10000 + Math.random() * 90000)}`,
    full_name: '',
    gender: 'Male',
    age_years: undefined,
    referral_doctor: '',
  });

  // Load patients and approved templates
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoadingTemplates(true);
        const [ptsData, tmplData] = await Promise.all([
          api.getPatients(),
          api.getTemplatesList({ only_approved: true })
        ]);
        setPatients(ptsData);
        setTemplates(tmplData);

        const requestedTplId = searchParams.get('template');
        if (requestedTplId) {
          const matchedTpl = tmplData.find((t) => t.id === requestedTplId);
          if (matchedTpl) {
            setTemplateId(matchedTpl.id);
            if (!matchedTpl.is_built_in) {
              setSelectedCategory('custom');
            } else if (matchedTpl.category) {
              setSelectedCategory(matchedTpl.category);
            }
          }
        }

        if (selectedPatientId) {
          const match = ptsData.find((p) => p.id === selectedPatientId);
          if (match && match.referral_doctor) {
            setReferralDoctor(match.referral_doctor);
          }
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load initial configuration');
      } finally {
        setLoadingTemplates(false);
      }
    };
    fetchData();
  }, [selectedPatientId]);

  // Handle patient change
  const handlePatientChange = (pId: string) => {
    setSelectedPatientId(pId);
    const match = patients.find((p) => p.id === pId);
    if (match) {
      if (match.referral_doctor) setReferralDoctor(match.referral_doctor);
      // Auto-suggest gender-aligned template if in abdomen & pelvis
      if (selectedCategory === 'abdomen_pelvis') {
        if (match.gender.toLowerCase() === 'female') {
          setTemplateId('usg-abdomen-pelvis-female');
        } else if (match.gender.toLowerCase() === 'male') {
          setTemplateId('usg-abdomen-pelvis-male');
        }
      }
    }
  };

  // Filter templates by category and laterality
  const filteredTemplates = useMemo(() => {
    return templates.filter((t) => {
      if (selectedCategory && selectedCategory !== 'all') {
        if (selectedCategory === 'custom') {
          if (t.category !== 'custom' && t.is_built_in) return false;
        } else if (t.category !== selectedCategory) {
          return false;
        }
      }
      if (selectedLaterality && selectedLaterality !== 'all') {
        if (t.laterality && t.laterality !== 'not_applicable' && t.laterality !== selectedLaterality) {
          return false;
        }
      }
      return true;
    });
  }, [templates, selectedCategory, selectedLaterality]);

  // When category changes, auto-select first matching template if current not in filtered list
  const handleCategorySelect = (catKey: string) => {
    setSelectedCategory(catKey);
    setSelectedLaterality('all');
    const available = templates.filter((t) =>
      catKey === 'custom' ? t.category === 'custom' || !t.is_built_in : t.category === catKey
    );
    if (available.length > 0) {
      const match = patients.find((p) => p.id === selectedPatientId);
      if (catKey === 'abdomen_pelvis' && match) {
        if (match.gender.toLowerCase() === 'female') {
          setTemplateId('usg-abdomen-pelvis-female');
          return;
        } else {
          setTemplateId('usg-abdomen-pelvis-male');
          return;
        }
      }
      setTemplateId(available[0].id);
    }
  };

  const handleQuickRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickPatient.full_name.trim() || !quickPatient.patient_id.trim()) {
      alert('Patient ID and Full Name are required.');
      return;
    }

    try {
      const created = await api.createPatient(quickPatient);
      setPatients([created, ...patients]);
      setSelectedPatientId(created.id);
      if (created.referral_doctor) setReferralDoctor(created.referral_doctor);
      if (selectedCategory === 'abdomen_pelvis') {
        if (created.gender.toLowerCase() === 'female') {
          setTemplateId('usg-abdomen-pelvis-female');
        } else {
          setTemplateId('usg-abdomen-pelvis-male');
        }
      }
      setShowQuickRegister(false);
    } catch (err: any) {
      alert(err.message || 'Failed to register patient');
    }
  };

  const handleCreateReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) {
      setError('Select or register a patient before creating a study.');
      return;
    }
    if (!templateId) {
      alert('Please select an ultrasound examination protocol template.');
      return;
    }
    try {
      setSubmitting(true);
      setError(null);
      const rep = await api.createReport({
        template_id: templateId,
        patient_id: selectedPatientId,
        referral_doctor: referralDoctor || null,
        report_date: reportDate,
      });
      navigate(`/reports/${rep.id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to create report');
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Initialize Ultrasound Examination</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Select patient demographics and examination protocol to open the dual-pane clinical reporting workspace
        </p>
      </div>

      {error && (
        <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleCreateReport} className="bg-white border border-slate-200 rounded-xl shadow-xs p-5 space-y-5">
        {/* Step 1: Patient Selection */}
        <div className="space-y-3 pb-4 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <Users className="w-4 h-4 text-teal-600" />
              1. Patient Demographics
            </label>
            <button
              type="button"
              onClick={() => setShowQuickRegister(!showQuickRegister)}
              className="text-xs font-semibold text-teal-700 hover:text-teal-800 flex items-center gap-1 cursor-pointer"
            >
              <UserPlus className="w-3.5 h-3.5" />
              {showQuickRegister ? 'Select Existing Patient' : 'Register New Patient'}
            </button>
          </div>

          {!showQuickRegister ? (
            <div>
              <select
                value={selectedPatientId}
                onChange={(e) => handlePatientChange(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs text-slate-800 bg-white focus:outline-none focus:border-teal-500"
              >
                <option value="">[ Select a Registered Patient ]</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.patient_id}) — {p.gender} {p.age_years ? `• ${p.age_years} yrs` : ''}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg space-y-2.5">
              <div className="text-xs font-bold text-slate-800">Quick Patient Registration</div>
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Patient ID / MRN *</label>
                  <input
                    type="text"
                    required
                    value={quickPatient.patient_id}
                    onChange={(e) => setQuickPatient({ ...quickPatient, patient_id: e.target.value })}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded text-xs focus:outline-none focus:border-teal-500"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Full Name *</label>
                  <input
                    type="text"
                    required
                    value={quickPatient.full_name}
                    onChange={(e) => setQuickPatient({ ...quickPatient, full_name: e.target.value })}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded text-xs focus:outline-none focus:border-teal-500"
                    placeholder="e.g. Rahul Sharma"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Gender *</label>
                  <select
                    value={quickPatient.gender}
                    onChange={(e) => setQuickPatient({ ...quickPatient, gender: e.target.value })}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded text-xs focus:outline-none focus:border-teal-500"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Age (Years)</label>
                  <input
                    type="number"
                    value={quickPatient.age_years ?? ''}
                    onChange={(e) =>
                      setQuickPatient({
                        ...quickPatient,
                        age_years: e.target.value ? parseInt(e.target.value) : undefined,
                      })
                    }
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded text-xs focus:outline-none focus:border-teal-500"
                    placeholder="45"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-1">
                <button
                  type="button"
                  onClick={handleQuickRegisterSubmit}
                  className="px-3 py-1 bg-slate-900 text-white text-xs font-semibold rounded hover:bg-slate-800 cursor-pointer"
                >
                  Save & Select Patient
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Step 2: Protocol Selection — 4 Examination Families */}
        <div className="space-y-3 pb-4 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-teal-600" />
              2. Examination Protocol Category *
            </label>
            <span className="text-[11px] font-semibold text-slate-400">
              {templates.length} Approved Templates in Library
            </span>
          </div>

          {/* 4 Examination Families Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {EXAM_CATEGORIES.map((cat) => {
              const Icon = cat.icon;
              const isSelected = selectedCategory === cat.key;
              const count = templates.filter((t) => t.category === cat.key).length;
              return (
                <div
                  key={cat.key}
                  onClick={() => handleCategorySelect(cat.key)}
                  className={`p-3.5 rounded-xl border-2 transition cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? 'border-teal-600 bg-teal-50/30 shadow-xs'
                      : 'border-slate-200 hover:border-slate-300 bg-white'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`p-1.5 rounded-lg ${isSelected ? 'bg-teal-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
                          <Icon className="w-4 h-4" />
                        </div>
                        <span className="font-bold text-xs text-slate-900">{cat.label}</span>
                      </div>
                      {isSelected && (
                        <div className="w-4 h-4 rounded-full bg-teal-600 text-white flex items-center justify-center">
                          <Check className="w-2.5 h-2.5" />
                        </div>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1.5 leading-relaxed">
                      {cat.description}
                    </p>
                  </div>
                  <div className="mt-2.5 flex items-center justify-between pt-1.5 border-t border-slate-100">
                    <span className="text-[10px] font-semibold text-slate-400">{count} Variations</span>
                    {isSelected && <span className="text-[10px] font-bold text-teal-700">Selected</span>}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Laterality Selector for Vascular Protocols */}
          {selectedCategory !== 'abdomen_pelvis' && (
            <div className="flex items-center gap-2 pt-1">
              <span className="text-xs font-semibold text-slate-600">Laterality Filter:</span>
              <div className="flex gap-1.5">
                {[
                  { key: 'all', label: 'All Protocols' },
                  { key: 'bilateral', label: 'Bilateral' },
                  { key: 'right', label: 'Right Only' },
                  { key: 'left', label: 'Left Only' }
                ].map((lat) => (
                  <button
                    key={lat.key}
                    type="button"
                    onClick={() => setSelectedLaterality(lat.key)}
                    className={`px-2.5 py-1 text-xs rounded-md font-semibold transition cursor-pointer ${
                      selectedLaterality === lat.key
                        ? 'bg-slate-900 text-white shadow-xs'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {lat.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Detailed Template Choice Selector */}
          <div className="space-y-1.5 pt-1">
            <label className="text-xs font-bold text-slate-700 block">
              Specific Document Template (Faithful Formatting):
            </label>
            {loadingTemplates ? (
              <div className="p-4 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
                <Clock className="w-4 h-4 animate-spin text-teal-600" />
                Loading approved templates...
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-500 text-center">
                No approved templates match the current filter. Select "All Protocols" or visit the Templates library.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-1.5 max-h-56 overflow-y-auto pr-1">
                {filteredTemplates.map((t) => {
                  const isChecked = templateId === t.id;
                  return (
                    <div
                      key={t.id}
                      onClick={() => setTemplateId(t.id)}
                      className={`p-2.5 rounded-lg border text-xs cursor-pointer flex items-center justify-between transition ${
                        isChecked
                          ? 'border-teal-600 bg-teal-50/40 font-semibold text-slate-900 shadow-xs'
                          : 'border-slate-200 hover:border-slate-300 bg-white text-slate-700'
                      }`}
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900">{t.name}</span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded font-bold uppercase bg-slate-100 text-slate-600 border border-slate-200">
                            {t.laterality ? t.laterality.replace('_', ' ') : '—'}
                          </span>
                          {t.table_type && t.table_type !== 'none' && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded font-semibold bg-teal-50 text-teal-700 border border-teal-200 flex items-center gap-1">
                              <FileSpreadsheet className="w-3 h-3" />
                              {t.table_type.replace('_', ' ')}
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-400 font-normal">
                          File: <span className="font-mono">{t.file_name}</span> · {t.sections.length} Sections
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {isChecked ? (
                          <div className="w-4 h-4 rounded-full bg-teal-600 text-white flex items-center justify-center">
                            <Check className="w-2.5 h-2.5" />
                          </div>
                        ) : (
                          <div className="w-4 h-4 rounded-full border border-slate-300"></div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Step 3: Study Context */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pb-1">
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-600 flex items-center gap-1">
              <Calendar className="w-3 h-3 text-slate-400" />
              Examination Date *
            </label>
            <input
              type="date"
              required
              value={reportDate}
              onChange={(e) => setReportDate(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 bg-white focus:outline-none focus:border-teal-500"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-600">
              Referral Doctor (Optional)
            </label>
            <input
              type="text"
              value={referralDoctor}
              onChange={(e) => setReferralDoctor(e.target.value)}
              placeholder="e.g. Dr. Sameer Joshi"
              className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 bg-white focus:outline-none focus:border-teal-500"
            />
          </div>
        </div>

        {/* Clinical Blank Slate Guarantee */}
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 flex items-start gap-2.5">
          <ShieldAlert className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
          <span>
            <strong>Zero Normal Invariant:</strong> The new report starts completely blank. Unmentioned anatomy,
            unrecorded arterial segments, and undictated impressions will not receive fabricated normal findings or placeholder leakage.
          </span>
        </div>

        {/* Submit Action */}
        <div className="pt-2 flex items-center justify-between gap-3">
          {!selectedPatientId ? (
            <span className="text-xs font-medium text-amber-700">
              Select or register a patient before creating a study.
            </span>
          ) : (
            <span />
          )}
          <button
            type="submit"
            disabled={submitting || !templateId || !selectedPatientId}
            className="flex items-center gap-2 px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg shadow-xs disabled:opacity-50 transition cursor-pointer"
          >
            <span>{submitting ? 'Creating Report...' : 'Open Reporting Workspace'}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </form>
    </div>
  );
};
