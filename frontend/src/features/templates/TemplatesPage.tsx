import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FilePlus,
  Upload,
  Search,
  CheckCircle2,
  Clock,
  Archive,
  Sliders,
  Layers,
  ChevronRight,
  X,
  Plus,
  Trash2,
  FileText,
  AlertCircle,
  Eye,
  GitBranch
} from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import type { TemplateDef } from '../../types';

export const TemplatesPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';
  const [templates, setTemplates] = useState<TemplateDef[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modals & Drawers
  const [showImportModal, setShowImportModal] = useState<boolean>(false);
  const [isBulkImport, setIsBulkImport] = useState<boolean>(false);
  const [importing, setImporting] = useState<boolean>(false);
  const [importError, setImportError] = useState<string | null>(null);

  // Configuration & Preview Modals
  const [previewTemplate, setPreviewTemplate] = useState<TemplateDef | null>(null);
  const [configTemplate, setConfigTemplate] = useState<TemplateDef | null>(null);
  const [configName, setConfigName] = useState<string>('');
  const [configCategory, setConfigCategory] = useState<string>('custom');
  const [configLaterality, setConfigLaterality] = useState<string>('not_applicable');
  const [configGender, setConfigGender] = useState<string>('Any');
  const [configSections, setConfigSections] = useState<{ order: number; key: string; label: string; heading: string }[]>([]);
  const [configTableType, setConfigTableType] = useState<string>('none');
  const [savingConfig, setSavingConfig] = useState<boolean>(false);

  const canManageTemplate = (tpl: TemplateDef) =>
    !tpl.is_built_in && (isAdmin || (!tpl.is_shared && tpl.created_by_user_id === user?.id));

  const fileInputRef = useRef<HTMLInputElement>(null);
  const bulkFileInputRef = useRef<HTMLInputElement>(null);

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      const data = await api.getTemplatesList({
        category: selectedCategory === 'all' ? undefined : selectedCategory,
        status: statusFilter === 'all' ? undefined : statusFilter,
        query: searchQuery || undefined,
      });
      setTemplates(data);
    } catch (err) {
      console.error('Failed to load templates', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, [selectedCategory, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchTemplates();
  };

  // Import Single DOCX
  const handleSingleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setImporting(true);
      setImportError(null);
      await api.importTemplate(file);
      setShowImportModal(false);
      fetchTemplates();
    } catch (err: any) {
      setImportError(err.message || 'Failed to import template');
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Bulk Import
  const handleBulkFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    try {
      setImporting(true);
      setImportError(null);
      const fileList = Array.from(files);
      await api.bulkImportTemplates(fileList);
      setShowImportModal(false);
      fetchTemplates();
    } catch (err: any) {
      setImportError(err.message || 'Failed to bulk import templates');
    } finally {
      setImporting(false);
      if (bulkFileInputRef.current) bulkFileInputRef.current.value = '';
    }
  };

  // Approve / Activate Template
  const handleApprove = async (tpl: TemplateDef) => {
    const promptMsg = isAdmin
      ? 'Approve this shared template for clinical report generation?'
      : 'Activate your personal custom template for creating clinical reports?';
    if (!confirm(promptMsg)) return;
    try {
      await api.approveTemplate(tpl.id, user?.display_name || 'Radiologist');
      fetchTemplates();
    } catch (err: any) {
      alert(err.message || 'Activation failed');
    }
  };

  // Create New Editable Version
  const handleVersion = async (tpl: TemplateDef) => {
    if (!confirm(`Create a new editable draft version (v${(tpl.version || 1) + 1}) of "${tpl.name}"?`)) return;
    try {
      await api.versionTemplate(tpl.id);
      fetchTemplates();
    } catch (err: any) {
      alert(err.message || 'Versioning failed');
    }
  };

  // Archive Template
  const handleArchive = async (id: string) => {
    if (!confirm('Archive this template? It will be hidden from new report creation.')) return;
    try {
      await api.archiveTemplate(id);
      fetchTemplates();
    } catch (err: any) {
      alert(err.message || 'Archive failed');
    }
  };

  // Open Configure Modal
  const openConfigModal = (tpl: TemplateDef) => {
    setConfigTemplate(tpl);
    setConfigName(tpl.name || '');
    setConfigCategory(tpl.category || 'custom');
    setConfigLaterality(tpl.laterality || 'not_applicable');
    setConfigGender(tpl.gender || 'Any');
    setConfigSections([...tpl.sections]);
    setConfigTableType(tpl.table_type || 'none');
  };

  const handleSaveConfig = async (andApprove = false) => {
    if (!configTemplate) return;
    try {
      setSavingConfig(true);
      await api.updateTemplate(configTemplate.id, {
        name: configName.trim() || configTemplate.name,
        gender: configGender,
        category: configCategory,
        laterality: configLaterality,
        sections: configSections,
        table_type: configTableType,
      });
      if (andApprove) {
        await api.approveTemplate(configTemplate.id, user?.display_name || 'Radiologist');
      }
      setConfigTemplate(null);
      fetchTemplates();
    } catch (err: any) {
      alert(err.message || 'Failed to save configuration');
    } finally {
      setSavingConfig(false);
    }
  };

  const categories = [
    { id: 'all', label: 'All Protocols' },
    { id: 'abdomen_pelvis', label: 'Abdomen & Pelvis' },
    { id: 'venous_doppler', label: 'Venous Doppler' },
    { id: 'arterial_doppler', label: 'Arterial Doppler' },
    { id: 'arteriovenous_doppler', label: 'Arteriovenous' },
    { id: 'custom', label: 'Custom / Imported' },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-5 pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Institutional Template Library</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Dynamic Word document management, layout extraction, and structured anatomical mapping
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setIsBulkImport(false); setShowImportModal(true); }}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs rounded-lg shadow-xs cursor-pointer transition"
          >
            <Upload className="w-3.5 h-3.5" />
            Import Template
          </button>
          <button
            onClick={() => { setIsBulkImport(true); setShowImportModal(true); }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold text-xs rounded-lg shadow-xs cursor-pointer transition"
          >
            <Layers className="w-3.5 h-3.5 text-purple-600" />
            Bulk Import
          </button>
          <button
            onClick={() => navigate('/reports/new')}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#0F172A] hover:bg-slate-800 text-white font-bold text-xs rounded-lg shadow-xs cursor-pointer transition"
          >
            <FilePlus className="w-3.5 h-3.5" />
            New Report
          </button>
        </div>
      </div>

      {/* Filter Bar & Search */}
      <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs space-y-2.5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <form onSubmit={handleSearchSubmit} className="flex-1 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search templates by title, examination, or filename..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-teal-500 focus:bg-white"
            />
          </form>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 font-semibold text-[11px]">STATUS:</span>
            {['all', 'approved', 'draft_config', 'archived'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded text-xs font-semibold capitalize cursor-pointer transition ${statusFilter === st
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
              >
                {st.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Category Tabs */}
        <div className="flex flex-wrap gap-1.5 pt-2 border-t border-slate-100">
          {categories.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedCategory(c.id)}
              className={`px-3 py-1 rounded text-xs font-bold transition cursor-pointer ${selectedCategory === c.id
                ? 'bg-teal-50 text-teal-800 border border-teal-200 shadow-xs'
                : 'text-slate-600 hover:bg-slate-50 border border-transparent'
                }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Template Grid */}
      {loading ? (
        <div className="py-20 text-center text-xs text-slate-500">Loading clinical template catalog...</div>
      ) : templates.length === 0 ? (
        <div className="py-16 text-center bg-white border border-slate-200 rounded-xl p-8 space-y-3">
          <AlertCircle className="w-8 h-8 text-slate-300 mx-auto" />
          <h3 className="font-bold text-slate-800 text-sm">
            {selectedCategory === 'custom'
              ? 'No custom templates imported yet'
              : 'No matching templates found'}
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {selectedCategory === 'custom'
              ? 'Import your own clinical Word (.docx) templates to extract headings, configure sections, version drafts, and generate structured reports.'
              : 'Import a new Word template or select another filter category.'}
          </p>
          <div className="pt-2">
            <button
              onClick={() => { setIsBulkImport(false); setShowImportModal(true); }}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg shadow-xs cursor-pointer transition"
            >
              <Upload className="w-3.5 h-3.5" />
              {selectedCategory === 'custom' ? 'Import Your First Template' : 'Import Template'}
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((tpl) => {
            const isApproved = tpl.status === 'APPROVED';
            const isDraft = tpl.status === 'DRAFT_CONFIG';
            const isArchived = tpl.status === 'ARCHIVED';

            return (
              <div
                key={tpl.id}
                className={`bg-white border rounded-xl shadow-xs p-4 flex flex-col justify-between transition hover:border-slate-300 ${isDraft ? 'border-amber-300 bg-amber-50/20' : 'border-slate-200'
                  }`}
              >
                <div className="space-y-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-[10px] font-mono tracking-tight px-2 py-0.5 rounded uppercase font-bold bg-slate-100 text-slate-700">
                      {tpl.category ? tpl.category.replace('_', ' ') : 'custom'}
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold flex items-center gap-1 ${isApproved
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : isDraft
                          ? 'bg-amber-100 text-amber-800 border border-amber-300'
                          : 'bg-slate-100 text-slate-500'
                        }`}
                    >
                      {isApproved && <CheckCircle2 className="w-3 h-3" />}
                      {isDraft && <Clock className="w-3 h-3" />}
                      {isArchived && <Archive className="w-3 h-3" />}
                      {tpl.status}
                    </span>
                  </div>

                  <div>
                    <h3 className="font-bold text-slate-900 text-xs leading-snug line-clamp-2">{tpl.name}</h3>
                    {tpl.file_name && (
                      <p className="text-[11px] font-mono text-slate-400 mt-1 truncate" title={tpl.file_name}>
                        📄 {tpl.file_name}
                      </p>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold">LATERALITY</span>
                      <span className="capitalize font-medium">{tpl.laterality || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold">SECTIONS</span>
                      <span className="font-medium">{tpl.section_count || tpl.sections.length} Fields</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold">TABLE TYPE</span>
                      <span className="font-medium">{tpl.table_type || 'None'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold">VERSION</span>
                      <span className="font-medium">v{tpl.version || 1}</span>
                    </div>
                  </div>
                </div>

                <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setPreviewTemplate(tpl)}
                      className="p-1.5 text-slate-500 hover:text-teal-700 hover:bg-slate-50 rounded cursor-pointer transition"
                      title="Preview Template Layout & Sections"
                    >
                      <Eye className="w-4 h-4" />
                    </button>

                    {canManageTemplate(tpl) ? (
                      <>
                        <button
                          onClick={() => openConfigModal(tpl)}
                          className="p-1.5 text-slate-500 hover:text-teal-600 hover:bg-slate-50 rounded cursor-pointer transition"
                          title="Configure & Edit Template"
                        >
                          <Sliders className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleVersion(tpl)}
                          className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-50 rounded cursor-pointer transition"
                          title="Create New Editable Version"
                        >
                          <GitBranch className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <span className="text-[10px] text-slate-400 font-medium px-1">
                        {tpl.is_built_in ? 'Institutional' : 'Shared'}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5">
                    {canManageTemplate(tpl) && isDraft && (
                      <button
                        onClick={() => handleApprove(tpl)}
                        className="px-2.5 py-1 text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold cursor-pointer"
                      >
                        {isAdmin ? 'Approve' : 'Activate'}
                      </button>
                    )}

                    {isApproved && (
                      <button
                        onClick={() => navigate(`/reports/new?template=${tpl.id}`)}
                        className="flex items-center gap-1 px-3 py-1 text-xs bg-teal-600 hover:bg-teal-700 text-white rounded font-semibold cursor-pointer shadow-xs transition"
                      >
                        Use <ChevronRight className="w-3 h-3" />
                      </button>
                    )}

                    {canManageTemplate(tpl) && !isArchived && (
                      <button
                        onClick={() => handleArchive(tpl.id)}
                        className="p-1.5 text-slate-400 hover:text-red-500 rounded cursor-pointer transition"
                        title="Archive Template"
                      >
                        <Archive className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-lg w-full p-5 shadow-2xl space-y-4 border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Upload className="w-4 h-4 text-teal-600" />
                {isBulkImport ? 'Bulk Import Word Templates' : 'Import Clinical Word Template'}
              </h3>
              <button
                onClick={() => setShowImportModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              Upload institutional <code>.docx</code> templates. SonoAxis automatically extracts headings,
              measurement tables, and placeholders without modifying original files.
            </p>

            {importError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg font-medium">
                {importError}
              </div>
            )}

            <div className="border-2 border-dashed border-slate-200 hover:border-teal-500 rounded-xl p-8 text-center space-y-3 transition bg-slate-50/50">
              <FileText className="w-8 h-8 text-teal-600 mx-auto" />
              <div>
                <p className="text-xs font-bold text-slate-800">
                  {isBulkImport ? 'Select multiple DOCX files' : 'Select a single DOCX file'}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">Accepts Microsoft Word .docx documents</p>
              </div>

              {isBulkImport ? (
                <input
                  type="file"
                  ref={bulkFileInputRef}
                  onChange={handleBulkFileSelect}
                  multiple
                  accept=".docx"
                  disabled={importing}
                  className="hidden"
                  id="bulk-file-input"
                />
              ) : (
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleSingleFileSelect}
                  accept=".docx"
                  disabled={importing}
                  className="hidden"
                  id="single-file-input"
                />
              )}

              <label
                htmlFor={isBulkImport ? 'bulk-file-input' : 'single-file-input'}
                className="inline-block px-4 py-2 bg-teal-600 text-white font-semibold text-xs rounded-lg shadow-xs cursor-pointer hover:bg-teal-700 transition"
              >
                {importing ? 'Extracting Structure...' : 'Browse Documents'}
              </label>
            </div>

            <div className="pt-2 text-right">
              <button
                onClick={() => setShowImportModal(false)}
                className="px-3.5 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg font-bold cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Configuration Drawer */}
      {configTemplate && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs flex justify-end z-50">
          <div className="bg-white w-full max-w-2xl h-full shadow-2xl flex flex-col justify-between overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="font-bold text-slate-900 text-base">Configure Template Mapping</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">{configTemplate.name}</p>
              </div>
              <button
                onClick={() => setConfigTemplate(null)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Scrollable Body */}
            <div className="p-5 overflow-y-auto space-y-5 flex-1 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="sm:col-span-2 space-y-1">
                  <label className="text-xs font-bold text-slate-700 block">TEMPLATE TITLE</label>
                  <input
                    type="text"
                    value={configName}
                    onChange={(e) => setConfigName(e.target.value)}
                    className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:bg-white focus:outline-none focus:border-teal-500"
                    placeholder="Template Title"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 block">CATEGORY</label>
                  <select
                    value={configCategory}
                    onChange={(e) => setConfigCategory(e.target.value)}
                    className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-teal-500"
                  >
                    <option value="custom">Custom / Imported</option>
                    <option value="abdomen_pelvis">Abdomen &amp; Pelvis</option>
                    <option value="venous_doppler">Venous Doppler</option>
                    <option value="arterial_doppler">Arterial Doppler</option>
                    <option value="arteriovenous_doppler">Arteriovenous Doppler</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 block">LATERALITY / GENDER</label>
                  <div className="flex gap-2">
                    <select
                      value={configLaterality}
                      onChange={(e) => setConfigLaterality(e.target.value)}
                      className="flex-1 px-2.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-teal-500"
                    >
                      <option value="not_applicable">N/A</option>
                      <option value="bilateral">Bilateral</option>
                      <option value="right">Right</option>
                      <option value="left">Left</option>
                    </select>
                    <select
                      value={configGender}
                      onChange={(e) => setConfigGender(e.target.value)}
                      className="w-24 px-2.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-teal-500"
                    >
                      <option value="Any">Any</option>
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-700 block">MEASUREMENT TABLE TYPE</label>
                <select
                  value={configTableType}
                  onChange={(e) => setConfigTableType(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-teal-500"
                >
                  <option value="none">None (Pure narrative paragraphs)</option>
                  <option value="arterial_3col_table">3-Column Unilateral Table (Artery | PSV | Flow Pattern)</option>
                  <option value="arterial_5col_table">5-Column Bilateral Table (Artery | Right PSV | Left PSV | Right Flow | Left Flow)</option>
                  <option value="arterial_3col_tabs">3-Column Tab-Stop Paragraphs</option>
                  <option value="arterial_5col_tabs">5-Column Tab-Stop Paragraphs</option>
                  <option value="custom_table">Custom Extracted Table</option>
                </select>
              </div>

              {/* Canonical Sections Mapping */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-700">CANONICAL CLINICAL FIELDS ({configSections.length})</label>
                  <button
                    onClick={() => {
                      const newOrder = configSections.length + 1;
                      setConfigSections([
                        ...configSections,
                        { order: newOrder, key: `field_${newOrder}`, label: `Custom Field ${newOrder}`, heading: `Field ${newOrder}: ` }
                      ]);
                    }}
                    className="flex items-center gap-1 text-xs text-teal-600 font-bold hover:underline cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Field
                  </button>
                </div>

                <div className="space-y-2 max-h-96 overflow-y-auto pr-1 divide-y divide-slate-100">
                  {configSections.map((sec, idx) => (
                    <div key={idx} className="pt-2 flex items-center gap-2">
                      <span className="w-6 text-center text-xs font-mono font-bold text-slate-400">{sec.order}</span>
                      <input
                        type="text"
                        value={sec.label}
                        onChange={(e) => {
                          const updated = [...configSections];
                          updated[idx].label = e.target.value;
                          updated[idx].heading = `${e.target.value}: `;
                          setConfigSections(updated);
                        }}
                        className="flex-1 px-2.5 py-1 text-xs bg-slate-50 border border-slate-200 rounded focus:bg-white focus:outline-none focus:border-teal-500"
                        placeholder="Label"
                      />
                      <input
                        type="text"
                        value={sec.key}
                        onChange={(e) => {
                          const updated = [...configSections];
                          updated[idx].key = e.target.value;
                          setConfigSections(updated);
                        }}
                        className="w-32 px-2.5 py-1 text-xs font-mono bg-slate-50 border border-slate-200 rounded text-slate-500 focus:outline-none"
                        placeholder="key"
                      />
                      <button
                        onClick={() => {
                          const updated = configSections.filter((_, i) => i !== idx);
                          setConfigSections(updated.map((s, i) => ({ ...s, order: i + 1 })));
                        }}
                        className="p-1 text-slate-400 hover:text-red-500 rounded cursor-pointer"
                        title="Remove Field"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
              <button
                onClick={() => setConfigTemplate(null)}
                className="px-3.5 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-200 rounded-lg cursor-pointer"
              >
                Cancel
              </button>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleSaveConfig(false)}
                  disabled={savingConfig}
                  className="px-3.5 py-1.5 text-xs font-bold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-lg shadow-xs cursor-pointer"
                >
                  Save Draft
                </button>
                <button
                  onClick={() => handleSaveConfig(true)}
                  disabled={savingConfig}
                  className="px-4 py-1.5 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg shadow-xs cursor-pointer"
                >
                  {isAdmin ? 'Save & Approve' : 'Save & Activate'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Template Preview Modal */}
      {previewTemplate && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-4xl w-full h-[80vh] shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-slate-900 text-sm">{previewTemplate.name}</h3>
                <p className="text-[11px] text-slate-500 font-mono">
                  v{previewTemplate.version || 1} · {previewTemplate.status} · {previewTemplate.section_count || previewTemplate.sections.length} sections
                </p>
              </div>
              <button
                onClick={() => setPreviewTemplate(null)}
                className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <iframe
              src={api.getTemplatePreviewUrl(previewTemplate.id)}
              title="Template Structure Preview"
              className="flex-1 w-full h-full border-none bg-white"
            />
          </div>
        </div>
      )}
    </div>
  );
};
