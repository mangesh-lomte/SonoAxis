import type {
  Patient,
  PatientCreate,
  Report,
  ReportListItem,
  Revision,
  TemplateDef,
  EngineStatus,
  DashboardStats,
  ExportStatus,
  OCRUploadResponse,
  OCRConfirmRequest,
  DoctorUser,
  LoginResponse,
  DoctorRole,
} from '../types';

const BASE_URL = '/api';

function getCookieValue(name: string): string | null {
  const prefix = `${name}=`;
  const parts = document.cookie.split(';');
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return null;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});
  const method = (options.method || 'GET').toUpperCase();

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrf = getCookieValue('sonoaxis_csrf');
    if (csrf && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrf);
    }
  }

  const response = await fetch(url, { ...options, headers, credentials: 'include' });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      if (errorJson && errorJson.detail !== undefined && errorJson.detail !== null) {
        const d = errorJson.detail;
        if (typeof d === 'string') {
          errorDetail = d;
        } else if (Array.isArray(d)) {
          errorDetail = d
            .map((item: any) => {
              if (typeof item === 'string') return item;
              if (item && typeof item === 'object') {
                const loc = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : '';
                return loc && item.msg ? `${loc}: ${item.msg}` : item.msg || JSON.stringify(item);
              }
              return String(item);
            })
            .join('; ');
        } else if (typeof d === 'object') {
          errorDetail = (d as any).message || JSON.stringify(d);
        } else {
          errorDetail = String(d);
        }
      }
    } catch {
      // Ignore json parse error
    }
    const err: any = new Error(errorDetail);
    err.status = response.status;
    throw err;
  }

  return response.json();
}

export const api = {
  // Authentication & Doctor Profile
  login: (username: string, password: string) =>
    request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<{ logged_out: boolean }>('/auth/logout', { method: 'POST' }),
  getMe: () => request<DoctorUser>('/auth/me'),
  updateProfile: (data: {
    full_name?: string;
    credentials?: string;
    designation?: string;
    department?: string;
    email?: string;
  }) => request<DoctorUser>('/auth/profile', { method: 'PUT', body: JSON.stringify(data) }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ changed: boolean }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),
  listUsers: () => request<DoctorUser[]>('/auth/users'),
  createUser: (data: {
    username: string;
    password: string;
    full_name: string;
    credentials?: string;
    designation?: string;
    role: DoctorRole;
    department?: string;
    email?: string;
  }) => request<DoctorUser>('/auth/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (
    userId: string,
    data: {
      full_name?: string;
      credentials?: string;
      designation?: string;
      role?: DoctorRole;
      department?: string;
      email?: string;
      is_active?: boolean;
      password?: string;
    }
  ) => request<DoctorUser>(`/auth/users/${userId}`, { method: 'PATCH', body: JSON.stringify(data) }),

  // Health & Status
  getHealth: () => request<{ status: string; app_name: string; version: string; database: string }>('/health'),
  getEngineStatus: () => request<EngineStatus>('/engine/status'),
  getExportsStatus: () => request<ExportStatus>('/exports/status'),
  getDashboardStats: () => request<DashboardStats>('/dashboard/stats'),

  // Patients
  getPatients: (query?: string) =>
    request<Patient[]>(`/patients${query ? `?query=${encodeURIComponent(query)}` : ''}`),
  getPatient: (id: string) => request<Patient>(`/patients/${id}`),
  createPatient: (data: PatientCreate) =>
    request<Patient>('/patients', { method: 'POST', body: JSON.stringify(data) }),
  updatePatient: (id: string, data: Partial<PatientCreate>) =>
    request<Patient>(`/patients/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePatient: (id: string, force = false) =>
    request<{ deleted: boolean }>(`/patients/${id}?force=${force}`, { method: 'DELETE' }),
  getPatientReports: (patientId: string) =>
    request<ReportListItem[]>(`/patients/${patientId}/reports`),

  // Reports
  getReports: (params?: { status?: string; template_id?: string; patient_id?: string; query?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.template_id) q.set('template_id', params.template_id);
    if (params?.patient_id) q.set('patient_id', params.patient_id);
    if (params?.query) q.set('query', params.query);
    const qs = q.toString();
    return request<ReportListItem[]>(`/reports${qs ? `?${qs}` : ''}`);
  },
  getReport: (id: string) => request<Report>(`/reports/${id}`),
  createReport: (data: { template_id: string; patient_id?: string | null; referral_doctor?: string | null; report_date?: string | null }) =>
    request<Report>('/reports', { method: 'POST', body: JSON.stringify(data) }),
  updateReport: (id: string, data: any) =>
    request<Report>(`/reports/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteReport: (id: string) =>
    request<{ deleted: boolean }>(`/reports/${id}`, { method: 'DELETE' }),

  // Revision & Review Workflow
  getReportRevisions: (id: string) =>
    request<Revision[]>(`/reports/${id}/revisions`),
  markReportReviewed: (id: string, reviewed_by: string, acknowledge_unresolved = true) =>
    request<Report>(`/reports/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ reviewed_by, acknowledge_unresolved }),
    }),
  revertReportToDraft: (id: string) =>
    request<Report>(`/reports/${id}/revert-draft`, { method: 'POST' }),

  // Audio & Structuring
  uploadReportAudio: (id: string, file: Blob | File, model_name?: string) => {
    const fd = new FormData();
    const filename = file instanceof File
      ? file.name
      : (file.type.includes('webm') ? 'dictation.webm' : 'dictation.wav');
    fd.append('file', file, filename);
    if (model_name) fd.append('model_name', model_name);
    return request<Report>(`/reports/${id}/audio`, { method: 'POST', body: fd });
  },
  addAdditionalRecording: (id: string, file: Blob | File, model_name?: string) => {
    const fd = new FormData();
    const filename = file instanceof File
      ? file.name
      : (file.type.includes('webm') ? 'additional_recording.webm' : 'additional_recording.wav');
    fd.append('file', file, filename);
    if (model_name) fd.append('model_name', model_name);
    return request<Report>(`/reports/${id}/recordings`, { method: 'POST', body: fd });
  },
  getReportRecordings: (id: string) =>
    request<any[]>(`/reports/${id}/recordings`),
  getPresets: (category?: string) =>
    request<Record<string, any>>(`/structuring/presets${category ? `?category=${category}` : ''}`),
  applySectionPreset: (id: string, section_key: string, preset_name?: string) =>
    request<Report>(`/reports/${id}/apply-preset`, {
      method: 'POST',
      body: JSON.stringify({ section_key, preset_name }),
    }),
  removeSectionPreset: (id: string, section_key: string) =>
    request<Report>(`/reports/${id}/remove-preset`, {
      method: 'POST',
      body: JSON.stringify({ section_key }),
    }),
  getReportChecklist: (id: string) =>
    request<{ report_id: string; category: string; items: any[] }>(`/structuring/checklist/${id}`),
  recalculateReport: (id: string) =>
    request<Report>(`/reports/${id}/recalculate`, { method: 'POST' }),
  structureReport: (id: string, transcript_text: string, force_regenerate = false, transcript_source?: string) =>
    request<Report>(`/reports/${id}/structure`, {
      method: 'POST',
      body: JSON.stringify({ transcript_text, force_regenerate, transcript_source }),
    }),
  assignReportUnassignedFinding: (
    reportId: string,
    unassigned_id: string,
    target_organ_key: string,
    custom_text?: string
  ) =>
    request<Report>(`/reports/${reportId}/assign-unassigned`, {
      method: 'POST',
      body: JSON.stringify({
        unassigned_id,
        target_organ_key,
        custom_text: custom_text || null,
      }),
    }),
  excludeReportUnassignedFinding: (
    reportId: string,
    unassigned_id: string,
    exclusion_reason: string
  ) =>
    request<Report>(`/reports/${reportId}/exclude-unassigned`, {
      method: 'POST',
      body: JSON.stringify({
        unassigned_id,
        exclusion_reason,
      }),
    }),
  assignUnassignedFinding: (
    report: any,
    unassigned_id: string,
    target_organ_key: string,
    custom_text?: string
  ) =>
    request<any>('/structuring/assign-unassigned', {
      method: 'POST',
      body: JSON.stringify({
        req: {
          unassigned_id,
          target_organ_key,
          custom_text: custom_text || null,
        },
        report,
      }),
    }),

  // Templates
  getTemplates: () =>
    request<{ templates: { id: string; name: string; gender: string; section_count: number }[] }>(
      '/structuring/templates'
    ),
  getTemplate: (id: string) => request<TemplateDef>(`/templates/${id}`),
  getTemplatesList: (params?: { category?: string; laterality?: string; status?: string; query?: string; only_approved?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set('category', params.category);
    if (params?.laterality) q.set('laterality', params.laterality);
    if (params?.status) q.set('status', params.status);
    if (params?.query) q.set('query', params.query);
    if (params?.only_approved) q.set('only_approved', 'true');
    const qs = q.toString();
    return request<TemplateDef[]>(`/templates${qs ? `?${qs}` : ''}`);
  },
  importTemplate: (file: File, custom_name?: string, category?: string) => {
    const fd = new FormData();
    fd.append('file', file);
    if (custom_name) fd.append('custom_name', custom_name);
    if (category) fd.append('category', category);
    return request<TemplateDef>('/templates/import', { method: 'POST', body: fd });
  },
  bulkImportTemplates: (files: File[]) => {
    const fd = new FormData();
    for (const f of files) {
      fd.append('files', f);
    }
    return request<TemplateDef[]>('/templates/bulk-import', { method: 'POST', body: fd });
  },
  extractTemplateStructure: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<any>('/templates/extract-structure', { method: 'POST', body: fd });
  },
  updateTemplate: (id: string, data: any) =>
    request<TemplateDef>(`/templates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  approveTemplate: (id: string, approved_by = 'Clinical Director') =>
    request<TemplateDef>(`/templates/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by }),
    }),
  archiveTemplate: (id: string) =>
    request<TemplateDef>(`/templates/${id}/archive`, { method: 'POST' }),
  versionTemplate: (id: string) =>
    request<TemplateDef>(`/templates/${id}/version`, { method: 'POST' }),
  getTemplatePreviewUrl: (id: string) => `/api/templates/${id}/preview`,

  // Settings & Backups
  getSettings: () => request<{ settings: Record<string, any> }>('/settings'),
  updateSettings: (settings: Record<string, any>) =>
    request<{ settings: Record<string, any> }>('/settings', {
      method: 'PUT',
      body: JSON.stringify({ settings }),
    }),
  getBackups: () => request<{ backups: any[] }>('/backups'),
  createBackup: () => request<any>('/backups', { method: 'POST' }),

  // Export & Preview URLs
  getReportPreviewUrl: (id: string) => `/api/reports/${id}/preview`,
  getReportDocxUrl: (id: string) => `/api/reports/${id}/export/docx`,
  getReportPdfUrl: (id: string) => `/api/reports/${id}/export/pdf`,

  // OCR & Machine Printouts
  uploadMachinePrintout: (reportId: string, formData: FormData) =>
    request<OCRUploadResponse>(`/reports/${reportId}/ocr/upload`, {
      method: 'POST',
      body: formData,
    }),
  confirmOCRMeasurements: (reportId: string, payload: OCRConfirmRequest) =>
    request<Report>(`/reports/${reportId}/ocr/confirm`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
