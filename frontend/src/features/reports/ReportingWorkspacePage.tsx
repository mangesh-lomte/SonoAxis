import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Mic,
  Square,
  Upload,
  RotateCcw,
  Sparkles,
  Save,
  CheckCircle2,
  AlertTriangle,
  Eye,
  Download,
  History,
  X,
  Clock,
  FileText,
  Volume2,
  User,
  Calendar,
  Plus,
  Trash2,
  Activity,
  HeartPulse,
  Play,
  Calculator,
  Edit3,
  Camera
} from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { AudioPlayerBar } from './AudioPlayerBar';
import { AnatomicalChecklistPanel } from './AnatomicalChecklistPanel';
import { NormalPresetsModal } from './NormalPresetsModal';
import { AdvancedMeasurementEditorModal } from './AdvancedMeasurementEditorModal';
import { ScanMeasurementsModal } from './ScanMeasurementsModal';
import { recordingRecovery } from '../../utils/recordingRecovery';
import type { AudioDraft } from '../../utils/recordingRecovery';
import type {
  Report,
  Revision,
  Patient,
  TemplateDef,
  ArterialSegmentBiometry,
  IncompetentPerforatorItem,
  PresetItem,
  AnatomicalChecklistItem,
  ReportSection
} from '../../types';

const DEFAULT_ARTERIAL_SEGMENTS: { key: string; name: string }[] = [
  { key: 'cfa', name: 'Common femoral artery (CFA)' },
  { key: 'sfa', name: 'Superficial femoral artery (SFA)' },
  { key: 'dfa', name: 'Deep femoral artery (Profunda)' },
  { key: 'popliteal', name: 'Popliteal artery' },
  { key: 'ata', name: 'Anterior tibial artery (ATA)' },
  { key: 'pta', name: 'Posterior tibial artery (PTA)' },
  { key: 'peroneal', name: 'Peroneal artery' },
  { key: 'dpa', name: 'Dorsalis pedis artery (DPA)' }
];

export const ReportingWorkspacePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [report, setReport] = useState<Report | null>(null);
  const [templateDef, setTemplateDef] = useState<TemplateDef | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [isDirty, setIsDirty] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Transcript state & source attribution tracking
  const [transcript, setTranscript] = useState<string>('');
  const [transcriptSource, setTranscriptSource] = useState<'typed_transcript' | 'recorded_voice' | 'uploaded_audio'>('typed_transcript');
  const [showOriginalTranscript, setShowOriginalTranscript] = useState<boolean>(false);

  // Audio recording state
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordDuration, setRecordDuration] = useState<number>(0);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [transcribing, setTranscribing] = useState<boolean>(false);
  const [structuring, setStructuring] = useState<boolean>(false);

  // MediaRecorder refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<any>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<any>(null);

  // Modals state
  const [isPreviewOpen, setIsPreviewOpen] = useState<boolean>(false);
  const [isRevisionsOpen, setIsRevisionsOpen] = useState<boolean>(false);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState<boolean>(false);
  const [reviewerName, setReviewerName] = useState<string>(
    user?.display_name || user?.full_name || ''
  );
  const isRadiologist = user?.role === 'Radiologist';

  useEffect(() => {
    if (user?.display_name || user?.full_name) {
      setReviewerName(user.display_name || user.full_name);
    }
  }, [user]);

  const [assignError, setAssignError] = useState<string | null>(null);
  const [assigningId, setAssigningId] = useState<string | null>(null);
  const [excludingId, setExcludingId] = useState<string | null>(null);
  const [excludeReason, setExcludeReason] = useState<string>('');

  // Phase 10D: Audio sync, Multi-recording, Guidance & Presets
  const [seekTime, setSeekTime] = useState<number | null>(null);
  const [_currentPlaybackTime, setCurrentPlaybackTime] = useState<number>(0);
  const [recoveredDraft, setRecoveredDraft] = useState<AudioDraft | null>(null);
  const [checklist, setChecklist] = useState<AnatomicalChecklistItem[]>([]);
  const [presetsCatalog, setPresetsCatalog] = useState<Record<string, PresetItem>>({});
  const [activePresetModalSection, setActivePresetModalSection] = useState<ReportSection | null>(null);
  const [activeBiometryModalSection, setActiveBiometryModalSection] = useState<ReportSection | null>(null);
  const [isAddingSecondaryRecording, setIsAddingSecondaryRecording] = useState<boolean>(false);
  const [isScanModalOpen, setIsScanModalOpen] = useState<boolean>(false);

  // Load report data & patients & template definition
  const loadReport = async () => {
    if (!id) return;
    try {
      setLoading(true);
      setReport(null);
      setTranscript('');
      setAudioUrl(null);
      setShowOriginalTranscript(false);
      setIsDirty(false);
      setError(null);
      setAudioLevel(0);
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
        setIsRecording(false);
      }

      const [rep, pts] = await Promise.all([
        api.getReport(id),
        api.getPatients()
      ]);
      setReport(rep);
      setPatients(pts);
      setTranscript(rep.edited_transcript || rep.original_transcript || '');
      const recs = rep.recordings || [];
      if (recs.length > 0) {
        const lastFname = (recs[recs.length - 1]?.filename || '').toLowerCase();
        setTranscriptSource(lastFname.includes('dictation') || lastFname.includes('recording') ? 'recorded_voice' : 'uploaded_audio');
      } else {
        setTranscriptSource('typed_transcript');
      }

      // Load template definition for protocol-specific behavior
      try {
        const tmpl = await api.getTemplate(rep.template_id);
        setTemplateDef(tmpl);
      } catch (e) {
        setTemplateDef(null);
      }

      // Check for recovered audio draft
      recordingRecovery.getDraft(id).then((draft) => {
        if (draft && draft.blob) {
          setRecoveredDraft(draft);
        }
      });

      // Load checklist & presets
      try {
        const [chk, presets] = await Promise.all([
          api.getReportChecklist(id),
          api.getPresets(),
        ]);
        if (chk && chk.items) setChecklist(chk.items);
        if (presets) setPresetsCatalog(presets);
      } catch (e) {
        console.warn('Failed to load guidance/presets:', e);
      }

      setIsDirty(false);
      setError(null);
    } catch (err: any) {
      setReport(null);
      setError(err.message || 'Failed to load report workspace');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
    return () => {
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
      }
    };
  }, [id]);

  // Audio Recording with MediaRecorder & Web Audio Analyser
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: true,
        }
      });
      audioChunksRef.current = [];

      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      const analyser = audioCtx.createAnalyser();
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);
      analyser.fftSize = 64;

      audioContextRef.current = audioCtx;
      analyserRef.current = analyser;

      const updateMeter = () => {
        if (!analyserRef.current) return;
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((acc, val) => acc + val, 0) / dataArray.length;
        setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
        animationFrameRef.current = requestAnimationFrame(updateMeter);
      };
      updateMeter();

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';
      const mr = new MediaRecorder(stream, { mimeType });

      mr.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
          const activeMime = mediaRecorderRef.current?.mimeType || 'audio/webm';
          const currentBlob = new Blob(audioChunksRef.current, { type: activeMime });
          if (id) {
            recordingRecovery.saveDraft(id, currentBlob, recordDuration);
          }
        }
      };

      mr.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
        if (audioContextRef.current) audioContextRef.current.close();
        setAudioLevel(0);

        const activeMime = mediaRecorderRef.current?.mimeType || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: activeMime });
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);

        if (isAddingSecondaryRecording) {
          await uploadAdditionalRecording(blob);
        } else {
          await uploadAndTranscribeAudio(blob);
        }
        if (id) {
          await recordingRecovery.clearDraft(id);
          setRecoveredDraft(null);
        }
      };

      mr.start(250);
      mediaRecorderRef.current = mr;
      setIsRecording(true);
      setRecordDuration(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordDuration((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      alert(`Microphone access error: ${err.message}. Please allow microphone permissions in your browser.`);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    }
  };

  const refreshChecklist = async () => {
    if (!id) return;
    try {
      const chk = await api.getReportChecklist(id);
      if (chk && chk.items) setChecklist(chk.items);
    } catch (e) {
      console.warn('Failed to refresh anatomical checklist:', e);
    }
  };

  const uploadAndTranscribeAudio = async (blob: Blob, srcMode: 'recorded_voice' | 'uploaded_audio' = 'recorded_voice') => {
    if (!id) return;
    try {
      setTranscribing(true);
      const updatedRep = await api.uploadReportAudio(id, blob, 'small.en');
      setReport(updatedRep);
      setTranscript(updatedRep.edited_transcript || updatedRep.original_transcript || '');
      setTranscriptSource(srcMode);
      setIsDirty(true);
      if (id) await recordingRecovery.clearDraft(id);
      setRecoveredDraft(null);
    } catch (err: any) {
      alert(`Transcription error: ${err.message}`);
    } finally {
      setTranscribing(false);
    }
  };

  const uploadAdditionalRecording = async (blob: Blob) => {
    if (!id) return;
    try {
      setTranscribing(true);
      const updatedRep = await api.addAdditionalRecording(id, blob, 'small.en');
      setReport(updatedRep);
      setTranscript(updatedRep.edited_transcript || updatedRep.original_transcript || '');
      setTranscriptSource('recorded_voice');
      setIsDirty(false);
      if (id) {
        await recordingRecovery.clearDraft(id);
        setRecoveredDraft(null);
        await refreshChecklist();
      }
    } catch (err: any) {
      alert(`Secondary recording error: ${err.message}`);
    } finally {
      setTranscribing(false);
      setIsAddingSecondaryRecording(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    setAudioUrl(URL.createObjectURL(file));
    if (isAddingSecondaryRecording) {
      await uploadAdditionalRecording(file);
    } else {
      await uploadAndTranscribeAudio(file, 'uploaded_audio');
    }
  };

  const handleRestoreDraft = async () => {
    if (!recoveredDraft) return;
    setAudioUrl(URL.createObjectURL(recoveredDraft.blob));
    await uploadAndTranscribeAudio(recoveredDraft.blob);
  };

  const handleDiscardDraft = async () => {
    if (!id) return;
    await recordingRecovery.clearDraft(id);
    setRecoveredDraft(null);
  };

  const handleApplyPreset = async (sectionKey: string, presetName: string) => {
    if (!id) return;
    try {
      const updated = await api.applySectionPreset(id, sectionKey, presetName);
      setReport(updated);
      setIsDirty(false);
      const chk = await api.getReportChecklist(id);
      if (chk && chk.items) setChecklist(chk.items);
    } catch (err: any) {
      alert(`Failed to apply preset: ${err.message}`);
    }
  };

  const handleRemovePreset = async (sectionKey: string) => {
    if (!id) return;
    try {
      const updated = await api.removeSectionPreset(id, sectionKey);
      setReport(updated);
      setIsDirty(false);
      const chk = await api.getReportChecklist(id);
      if (chk && chk.items) setChecklist(chk.items);
    } catch (err: any) {
      alert(`Failed to remove preset: ${err.message}`);
    }
  };

  const handleRecalculateBiometry = async () => {
    if (!id) return;
    try {
      const updated = await api.recalculateReport(id);
      setReport(updated);
      setIsDirty(false);
      await refreshChecklist();
    } catch (err: any) {
      alert(`Recalculation error: ${err.message}`);
    }
  };

  const handleSaveSectionModal = async (updatedSec: ReportSection) => {
    if (!report || !report.structured_findings || !id) return;
    const updatedSections = (report.structured_findings.sections || []).map((s) =>
      s.key === updatedSec.key ? updatedSec : s
    );
    const newStructured = {
      ...report.structured_findings,
      sections: updatedSections,
    };
    const updatedRep = await api.updateReport(id, {
      structured_findings: newStructured,
    });
    setReport(updatedRep);
    setIsDirty(false);
    await refreshChecklist();
  };

  // Explicit Structuring Action
  const handleGenerateStructuredDraft = async () => {
    if (!id || !transcript.trim()) {
      alert('Transcript is empty. Type findings or record audio before generating a structured draft.');
      return;
    }

    try {
      setStructuring(true);
      const updated = await api.structureReport(id, transcript, true, transcriptSource);
      setReport(updated);
      setIsDirty(false);
      await refreshChecklist();
    } catch (err: any) {
      alert(`Structuring failed: ${err.message}`);
    } finally {
      setStructuring(false);
    }
  };

  // Section Findings Editing (syncs checklist live)
  const handleSectionTextChange = (key: string, newText: string) => {
    if (!report || !report.structured_findings) return;
    const textVal = newText.trim() ? newText : null;
    const present = Boolean(textVal);
    const updatedSections = (report.structured_findings.sections || []).map((s) => {
      if (s.key === key) {
        return {
          ...s,
          text: textVal,
          is_present: present,
          source_type: present ? 'manual' : null,
        };
      }
      return s;
    });

    setReport({
      ...report,
      structured_findings: {
        ...report.structured_findings,
        sections: updatedSections,
      },
    });
    setChecklist((prev) =>
      prev.map((item) =>
        item.key === key
          ? {
              ...item,
              is_present: present,
              status: present ? 'manually_entered' : 'not_documented',
              source_type: present ? 'manual' : null,
              summary_text: textVal,
            }
          : item
      )
    );
    setIsDirty(true);
  };

  const handleClearSection = (key: string) => {
    handleSectionTextChange(key, '');
  };

  const handleImpressionChange = (val: string) => {
    if (!report) return;
    const impVal = val.trim() ? val : null;
    setReport({
      ...report,
      impression: impVal,
      structured_findings: report.structured_findings
        ? {
            ...report.structured_findings,
            impression: impVal,
          }
        : null,
    });
    setIsDirty(true);
  };

  const handleClinicalProfileChange = (val: string) => {
    if (!report) return;
    const textVal = val.trim() ? val : null;
    const currentSf = report.structured_findings || {
      sections: [],
      impression: null,
      unassigned_findings: [],
      superseded_history: []
    };
    const currentVasc = currentSf.vascular_biometry || {};
    setReport({
      ...report,
      clinical_profile: textVal,
      structured_findings: {
        ...currentSf,
        clinical_profile: textVal,
        vascular_biometry: {
          ...currentVasc,
          clinical_profile: textVal,
        }
      }
    });
    setIsDirty(true);
  };

  const handleRecommendationsChange = (val: string) => {
    if (!report) return;
    const textVal = val.trim() ? val : null;
    const currentSf = report.structured_findings || {
      sections: [],
      impression: null,
      unassigned_findings: [],
      superseded_history: []
    };
    const currentVasc = currentSf.vascular_biometry || {};
    setReport({
      ...report,
      recommendations: textVal,
      structured_findings: {
        ...currentSf,
        recommendations: textVal,
        vascular_biometry: {
          ...currentVasc,
          recommendations: textVal,
        }
      }
    });
    setIsDirty(true);
  };

  // Arterial Biometry Table handlers
  const handleArterialCellChange = (
    index: number,
    field: 'psv_right' | 'psv_left' | 'flow_pattern_right' | 'flow_pattern_left',
    value: any
  ) => {
    if (!report) return;
    const currentSf = report.structured_findings || {
      sections: [],
      impression: null,
      unassigned_findings: [],
      superseded_history: []
    };
    const currentVasc = currentSf.vascular_biometry || {};
    const currentTable = [...(currentVasc.arterial_table || [])];

    if (currentTable[index]) {
      currentTable[index] = {
        ...currentTable[index],
        [field]: value
      };
    }

    setReport({
      ...report,
      structured_findings: {
        ...currentSf,
        vascular_biometry: {
          ...currentVasc,
          arterial_table: currentTable
        }
      }
    });
    setIsDirty(true);
  };

  const handleAddArterialRow = () => {
    if (!report) return;
    const currentSf = report.structured_findings || {
      sections: [],
      impression: null,
      unassigned_findings: [],
      superseded_history: []
    };
    const currentVasc = currentSf.vascular_biometry || {};
    const currentTable = [...(currentVasc.arterial_table || [])];
    const newIdx = currentTable.length + 1;
    currentTable.push({
      segment_key: `custom_artery_${newIdx}`,
      segment_name: `Arterial Segment ${newIdx}`,
      psv_right: null,
      psv_left: null,
      flow_pattern_right: null,
      flow_pattern_left: null
    });

    setReport({
      ...report,
      structured_findings: {
        ...currentSf,
        vascular_biometry: {
          ...currentVasc,
          arterial_table: currentTable
        }
      }
    });
    setIsDirty(true);
  };

  const handleDeleteArterialRow = (index: number) => {
    if (!report) return;
    const currentSf = report.structured_findings || {
      sections: [],
      impression: null,
      unassigned_findings: [],
      superseded_history: []
    };
    const currentVasc = currentSf.vascular_biometry || {};
    const currentTable = [...(currentVasc.arterial_table || [])];
    currentTable.splice(index, 1);

    setReport({
      ...report,
      structured_findings: {
        ...currentSf,
        vascular_biometry: {
          ...currentVasc,
          arterial_table: currentTable
        }
      }
    });
    setIsDirty(true);
  };

  // Venous Perforator Card handlers
  const handleAddPerforator = () => {
    if (!report) return;
    const currentSf = report.structured_findings || {
      sections: [],
      impression: null,
      unassigned_findings: [],
      superseded_history: []
    };
    const currentVasc = currentSf.vascular_biometry || {};
    const currentPerfs = [...(currentVasc.incompetent_perforators || [])];
    const defaultLat: 'Right' | 'Left' = report.template_id.includes('left') ? 'Left' : 'Right';

    currentPerfs.push({
      laterality: defaultLat,
      diameter_mm: null,
      aspect: 'Medial',
      distance_cm: null,
      landmark: 'above medial malleolus',
      raw_text: 'Incompetent perforator'
    });

    setReport({
      ...report,
      structured_findings: {
        ...currentSf,
        vascular_biometry: {
          ...currentVasc,
          incompetent_perforators: currentPerfs
        }
      }
    });
    setIsDirty(true);
  };

  const handleUpdatePerforator = (index: number, updatedItem: IncompetentPerforatorItem) => {
    if (!report) return;
    const currentSf = report.structured_findings || {
      sections: [],
      impression: null,
      unassigned_findings: [],
      superseded_history: []
    };
    const currentVasc = currentSf.vascular_biometry || {};
    const currentPerfs = [...(currentVasc.incompetent_perforators || [])];
    currentPerfs[index] = updatedItem;

    setReport({
      ...report,
      structured_findings: {
        ...currentSf,
        vascular_biometry: {
          ...currentVasc,
          incompetent_perforators: currentPerfs
        }
      }
    });
    setIsDirty(true);
  };

  const handleDeletePerforator = (index: number) => {
    if (!report) return;
    const currentSf = report.structured_findings || {
      sections: [],
      impression: null,
      unassigned_findings: [],
      superseded_history: []
    };
    const currentVasc = currentSf.vascular_biometry || {};
    const currentPerfs = [...(currentVasc.incompetent_perforators || [])];
    currentPerfs.splice(index, 1);

    setReport({
      ...report,
      structured_findings: {
        ...currentSf,
        vascular_biometry: {
          ...currentVasc,
          incompetent_perforators: currentPerfs
        }
      }
    });
    setIsDirty(true);
  };

  // Save report
  const handleSave = async () => {
    if (!report || !id) return;
    try {
      setSaving(true);
      const payload = {
        edited_transcript: transcript,
        structured_findings: report.structured_findings,
        impression: report.impression,
        referral_doctor: report.referral_doctor,
        report_date: report.report_date,
        expected_revision_number: report.revision_number,
      };
      const updated = await api.updateReport(id, payload);
      setReport(updated);
      setIsDirty(false);
      await refreshChecklist();
    } catch (err: any) {
      if (err.status === 409) {
        alert('Concurrency Conflict: This report was updated elsewhere. Reloading latest saved revision.');
        await loadReport();
      } else {
        alert(`Failed to save report: ${err.message}`);
      }
    } finally {
      setSaving(false);
    }
  };

  // Review Workflow
  const handleMarkReviewed = async () => {
    if (!report || !id) return;
    if (isDirty) {
      await handleSave();
    }
    try {
      const updated = await api.markReportReviewed(id, reviewerName, false);
      setReport(updated);
      setIsReviewModalOpen(false);
      setIsDirty(false);
    } catch (err: any) {
      alert(`Review sign-off failed: ${err.message}`);
    }
  };

  const handleRevertDraft = async () => {
    if (!report || !id) return;
    if (!confirm('Revert this clinically verified report back to DRAFT?')) return;
    try {
      const updated = await api.revertReportToDraft(id);
      setReport(updated);
      setIsDirty(false);
    } catch (err: any) {
      alert(`Revert failed: ${err.message}`);
    }
  };

  // Unassigned finding manual assignment (persisted immediately)
  const handleAssignUnassigned = async (unassignedId: string, targetKey: string) => {
    if (!report || !id || !report.structured_findings || !targetKey) return;
    setAssignError(null);
    setAssigningId(unassignedId);
    try {
      if (isDirty) {
        await handleSave();
      }
      const updatedReport = await api.assignReportUnassignedFinding(id, unassignedId, targetKey);
      setReport(updatedReport);
      setIsDirty(false);
      await refreshChecklist();
    } catch (err: any) {
      const msg = typeof err?.message === 'string' ? err.message : 'Unable to assign clinical finding.';
      setAssignError(`Assignment failed: ${msg}`);
    } finally {
      setAssigningId(null);
    }
  };

  const handleExcludeUnassigned = async (unassignedId: string) => {
    if (!report || !id) return;
    const reason = excludeReason.trim();
    if (reason.length < 3) {
      setAssignError('Please enter a documented clinical exclusion reason (at least 3 characters).');
      return;
    }
    setAssignError(null);
    setAssigningId(unassignedId);
    try {
      if (isDirty) {
        await handleSave();
      }
      const updatedReport = await api.excludeReportUnassignedFinding(id, unassignedId, reason);
      setReport(updatedReport);
      setIsDirty(false);
      setExcludingId(null);
      setExcludeReason('');
      await refreshChecklist();
    } catch (err: any) {
      const msg = typeof err?.message === 'string' ? err.message : 'Unable to exclude clinical finding.';
      setAssignError(`Exclusion failed: ${msg}`);
    } finally {
      setAssigningId(null);
    }
  };

  const openRevisions = async () => {
    if (!id) return;
    try {
      const revs = await api.getReportRevisions(id);
      setRevisions(revs);
      setIsRevisionsOpen(true);
    } catch (err: any) {
      alert(`Failed to load revisions: ${err.message}`);
    }
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Protocol determination
  const category = templateDef?.category || report?.category || 'abdomen_pelvis';
  const isVascular = category !== 'abdomen_pelvis';
  const isArterial = category === 'arterial_doppler' || category === 'arteriovenous_doppler' || templateDef?.table_type !== 'none';
  const isVenous = category === 'venous_doppler' || category === 'arteriovenous_doppler';
  const isUnilateralArterial = templateDef?.table_type === 'three_col_unilateral' || templateDef?.laterality === 'right' || templateDef?.laterality === 'left';

  // Ensure arterial table initialized with default segments if empty
  const activeArterialTable: ArterialSegmentBiometry[] = useMemo(() => {
    const currentTable = report?.structured_findings?.vascular_biometry?.arterial_table;
    if (currentTable && currentTable.length > 0) {
      return currentTable;
    }
    return DEFAULT_ARTERIAL_SEGMENTS.map((s) => ({
      segment_key: s.key,
      segment_name: s.name,
      psv_right: null,
      psv_left: null,
      flow_pattern_right: null,
      flow_pattern_left: null
    }));
  }, [report?.structured_findings?.vascular_biometry?.arterial_table]);

  const activePerforators: IncompetentPerforatorItem[] = useMemo(() => {
    return report?.structured_findings?.vascular_biometry?.incompetent_perforators || [];
  }, [report?.structured_findings?.vascular_biometry?.incompetent_perforators]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 text-slate-500 text-sm">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 animate-spin text-teal-600" />
          <span>Loading clinical reporting workspace...</span>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="max-w-xl mx-auto p-6 bg-red-50 border border-red-200 rounded-xl text-red-800 text-center space-y-3">
        <AlertTriangle className="w-8 h-8 text-red-600 mx-auto" />
        <div className="font-bold">Error Loading Report Workspace</div>
        <p className="text-sm">{error || 'Report record not found'}</p>
        <button
          onClick={() => navigate('/reports')}
          className="px-4 py-2 bg-red-700 text-white text-xs font-semibold rounded-lg hover:bg-red-800 cursor-pointer"
        >
          Return to Reports Registry
        </button>
      </div>
    );
  }

  const patient = report.patient_snapshot;
  const isDraft = report.status === 'DRAFT';
  const sections = report.structured_findings?.sections || [];
  const unassigned = report.structured_findings?.unassigned_findings || [];
  const superseded = report.structured_findings?.superseded_history || [];

  return (
    <div className="max-w-[1600px] mx-auto space-y-4">
      {/* TOP CONTROL BAR: Clinical Header & Actions */}
      <div className="bg-white border border-slate-200 rounded-xl px-5 py-3 shadow-xs flex flex-wrap items-center justify-between gap-3">
        {/* Left: Study Context */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-900 text-sm tracking-tight">{report.report_number || report.id.slice(0, 8)}</span>
            <span className="text-[11px] px-2 py-0.5 bg-slate-100 text-slate-700 font-semibold rounded border border-slate-200">
              {templateDef?.name || report.template_name || report.template_id}
            </span>
          </div>
          <span className="text-slate-300">|</span>
          <div className="text-xs text-slate-600 flex items-center gap-1.5">
            <span>Patient:</span>
            <strong className="text-slate-900 font-semibold">{patient?.full_name || report.patient_name || 'Anonymous'}</strong>
            <span className="text-slate-400 font-mono text-[11px]">({patient?.patient_id || '—'})</span>
          </div>
        </div>

        {/* Center: Draft vs Reviewed Pill & Rev counter */}
        <div className="flex items-center gap-2.5">
          <span
            className={`text-xs px-2.5 py-0.5 rounded font-bold tracking-wider uppercase flex items-center gap-1.5 ${
              isDraft
                ? 'bg-amber-100 text-amber-900 border border-amber-300'
                : 'bg-emerald-100 text-emerald-900 border border-emerald-300'
            }`}
          >
            {isDraft ? <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> : <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
            {report.status}
          </span>
          <span className="text-xs font-semibold text-slate-500 font-mono">Rev #{report.revision_number}</span>
          <span className="text-slate-300">|</span>
          <span className="text-xs">
            {isDirty ? (
              <span className="text-amber-600 font-semibold flex items-center gap-1">● Unsaved Edits</span>
            ) : (
              <span className="text-teal-600 font-medium">✓ Saved</span>
            )}
          </span>
        </div>

        {/* Right: Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setIsPreviewOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg cursor-pointer transition shadow-xs"
          >
            <Eye className="w-3.5 h-3.5 text-slate-500" />
            Preview
          </button>

          <button
            onClick={() => window.open(api.getReportDocxUrl(report.id), '_blank')}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg cursor-pointer transition shadow-xs"
          >
            <Download className="w-3.5 h-3.5 text-slate-500" />
            Word
          </button>

          <button
            onClick={() => window.open(api.getReportPdfUrl(report.id), '_blank')}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg cursor-pointer transition shadow-xs"
          >
            <Download className="w-3.5 h-3.5 text-slate-500" />
            PDF
          </button>

          <button
            onClick={() => setIsScanModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-teal-300 bg-teal-50 hover:bg-teal-100 text-teal-800 text-xs font-semibold rounded-lg cursor-pointer transition shadow-xs"
            title="Scan machine printout or screenshot (Local OCR)"
          >
            <Camera className="w-3.5 h-3.5 text-teal-600" />
            Scan
          </button>

          <button
            onClick={openRevisions}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg cursor-pointer transition shadow-xs"
          >
            <History className="w-3.5 h-3.5 text-slate-500" />
            Audit
          </button>

          <button
            onClick={handleSave}
            disabled={saving || !isDirty}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#0F172A] hover:bg-slate-900 text-white text-xs font-bold rounded-lg disabled:opacity-50 cursor-pointer shadow-xs transition"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? 'Saving...' : 'Save Draft'}
          </button>

          {isDraft ? (
            <button
              onClick={() => isRadiologist && setIsReviewModalOpen(true)}
              disabled={!isRadiologist}
              title={
                isRadiologist
                  ? 'Verify and finalize report'
                  : 'Clinical sign-off requires a Radiologist account'
              }
              className={`flex items-center gap-1.5 px-3.5 py-1.5 text-white text-xs font-bold rounded-lg shadow-xs transition ${
                isRadiologist
                  ? 'bg-emerald-600 hover:bg-emerald-700 cursor-pointer'
                  : 'bg-slate-400 cursor-not-allowed opacity-70'
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Mark Reviewed
            </button>
          ) : (
            <button
              onClick={() => isRadiologist && handleRevertDraft()}
              disabled={!isRadiologist}
              title={
                isRadiologist
                  ? 'Revert finalized report back to draft'
                  : 'Clinical review controls require a Radiologist account'
              }
              className={`flex items-center gap-1.5 px-3.5 py-1.5 border text-xs font-bold rounded-lg transition shadow-xs ${
                isRadiologist
                  ? 'border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 cursor-pointer'
                  : 'border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed'
              }`}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Revert to Draft
            </button>
          )}
        </div>
      </div>

      {/* Reviewer Invalidation Warning Alert */}
      {report.is_reviewed && isDirty && (
        <div className="p-3 bg-amber-50 border border-amber-300 rounded-xl flex items-center gap-3 text-amber-900 text-xs font-medium">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <div>
            <span className="font-bold">Reviewer Invalidation Warning:</span> This report was verified by <strong>{report.reviewed_by || 'Radiologist'}</strong>.
            Saving edits will automatically reset report status to <strong>DRAFT</strong> to maintain clinical audit integrity.
          </div>
        </div>
      )}

      {/* Phase 10D: Audio Recording Recovery Alert */}
      {recoveredDraft && (
        <div className="p-3 bg-amber-50 border border-amber-300 rounded-xl flex items-center justify-between text-xs text-amber-900 shadow-xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              <strong>Unsaved Audio Recording Recovered:</strong> An audio dictation ({recoveredDraft.durationSeconds}s) was recovered from your previous session.
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRestoreDraft}
              className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded text-xs shadow-xs transition cursor-pointer"
            >
              Restore & Transcribe
            </button>
            <button
              type="button"
              onClick={handleDiscardDraft}
              className="px-2.5 py-1 text-slate-600 hover:text-slate-800 border border-slate-300 rounded text-xs transition cursor-pointer"
            >
              Discard
            </button>
          </div>
        </div>
      )}

      {/* DUAL-PANE CLINICAL WORKSPACE: 40% (5 Cols) / 60% (7 Cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* ================= LEFT PANE: CLINICAL INPUT & DICTATION (5 COLS) ================= */}
        <div className="lg:col-span-5 space-y-4">
          {/* Card 1: Report Details */}
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
              <User className="w-4 h-4 text-slate-600" />
              <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wider">Report Details</h3>
            </div>

            <div className="space-y-2.5">
              {/* Patient */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-700">Patient</label>
                  <button
                    type="button"
                    onClick={() => navigate('/patients')}
                    className="text-xs text-teal-600 hover:text-teal-700 font-bold flex items-center gap-0.5 cursor-pointer"
                  >
                    + New Patient
                  </button>
                </div>
                <select
                  disabled
                  value={patient?.id || ''}
                  className="w-full px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none"
                >
                  <option value={patient?.id || ''}>
                    {patient ? `${patient.full_name} (${patient.patient_id})` : report.patient_name || 'Select a patient'}
                  </option>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.full_name} ({p.patient_id})
                    </option>
                  ))}
                </select>
              </div>

              {/* Study Category & Template */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">Study category</label>
                  <div className="w-full px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 capitalize font-medium truncate">
                    {category.replace(/_/g, ' ')}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">Study template</label>
                  <div className="w-full px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 font-medium truncate" title={templateDef?.name || report.template_name || report.template_id}>
                    {templateDef?.name || report.template_name || report.template_id}
                  </div>
                </div>
              </div>

              {/* Referral Doctor & Date */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">Referral doctor</label>
                  <input
                    type="text"
                    placeholder="Optional"
                    value={report.referral_doctor || ''}
                    onChange={(e) => {
                      setReport({ ...report, referral_doctor: e.target.value });
                      setIsDirty(true);
                    }}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-teal-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1 flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-slate-400" /> Report date
                  </label>
                  <input
                    type="text"
                    value={report.report_date}
                    onChange={(e) => {
                      setReport({ ...report, report_date: e.target.value });
                      setIsDirty(true);
                    }}
                    className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Local AI Dictation */}
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3.5">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-teal-600" />
                  <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wider">Local AI Dictation</h3>
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">100% on-premise inference · Audio and data stay local</p>
              </div>
              <span className="text-[10px] px-2 py-0.5 bg-teal-50 text-teal-700 font-semibold rounded border border-teal-200">
                Faster-Whisper
              </span>
            </div>

            {/* Status Box */}
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
                <span className="font-semibold text-slate-800 text-[11px]">Ready (CPU INT8)</span>
              </div>
              <span className="text-[11px] font-mono text-slate-500">Model: small.en</span>
            </div>

            {/* Dictation Textarea */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <label className="text-xs font-semibold text-slate-700">Dictation Transcript</label>
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
                    transcriptSource === 'recorded_voice'
                      ? 'bg-blue-50 text-blue-700 border-blue-200'
                      : transcriptSource === 'uploaded_audio'
                      ? 'bg-sky-50 text-sky-700 border-sky-200'
                      : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                  }`}>
                    {transcriptSource === 'recorded_voice'
                      ? 'Recorded Voice'
                      : transcriptSource === 'uploaded_audio'
                      ? 'Uploaded Audio'
                      : 'Typed / Pasted Transcript'}
                  </span>
                </div>
                {report.original_transcript && (
                  <button
                    type="button"
                    onClick={() => setShowOriginalTranscript(!showOriginalTranscript)}
                    className="text-[11px] text-teal-600 hover:underline font-semibold cursor-pointer"
                  >
                    {showOriginalTranscript ? 'Show Edited' : 'View Original Transcript'}
                  </button>
                )}
              </div>

              {!showOriginalTranscript ? (
                <textarea
                  rows={5}
                  value={transcript}
                  onChange={(e) => {
                    setTranscript(e.target.value);
                    if (!report.recordings || report.recordings.length === 0) {
                      setTranscriptSource('typed_transcript');
                    }
                    setIsDirty(true);
                  }}
                  placeholder="Type or dictate ultrasound findings. You can edit the text before processing with AI."
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-xs text-slate-800 leading-relaxed font-sans focus:outline-none focus:border-teal-500 bg-white placeholder-slate-400"
                />
              ) : (
                <div className="p-2.5 border border-slate-200 rounded-lg text-xs font-mono bg-slate-50 text-slate-600 leading-relaxed max-h-36 overflow-y-auto">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Original Unedited Transcript:</span>
                  {report.original_transcript}
                </div>
              )}
            </div>

            {/* Audio Recording & Upload Buttons */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                {!isRecording ? (
                  <button
                    type="button"
                    onClick={startRecording}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-800 font-semibold text-xs rounded-lg shadow-xs transition cursor-pointer"
                  >
                    <Mic className="w-3.5 h-3.5 text-teal-600" />
                    Record Audio
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={stopRecording}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-red-600 hover:bg-red-700 text-white font-bold text-xs rounded-lg shadow-xs transition cursor-pointer animate-pulse"
                  >
                    <Square className="w-3.5 h-3.5" />
                    Stop ({formatTimer(recordDuration)})
                  </button>
                )}

                <label className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-800 font-semibold text-xs rounded-lg shadow-xs cursor-pointer transition">
                  <Upload className="w-3.5 h-3.5 text-slate-600" />
                  Upload Audio
                  <input type="file" accept="audio/*" onChange={handleFileUpload} className="hidden" />
                </label>

                <button
                  type="button"
                  onClick={() => setIsScanModalOpen(true)}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-white border border-teal-200 hover:bg-teal-50 text-teal-800 font-semibold text-xs rounded-lg shadow-xs cursor-pointer transition"
                  title="Scan machine printout or screenshot (Local OCR)"
                >
                  <Camera className="w-3.5 h-3.5 text-teal-600" />
                  Scan OCR
                </button>
              </div>
            </div>

            {/* Active Recording Level Indicator */}
            {isRecording && (
              <div className="p-3 bg-red-50/70 border border-red-200 rounded-lg space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-red-800">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-600 animate-ping"></span>
                    Microphone Live...
                  </span>
                  <span className="font-mono text-xs">{formatTimer(recordDuration)}</span>
                </div>
                <div className="w-full bg-red-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-red-600 h-1.5 transition-all duration-75"
                    style={{ width: `${Math.max(5, audioLevel)}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Audio Playback Element & Multi-Recording Sync Player */}
            <div className="space-y-2">
              <AudioPlayerBar
                audioUrl={audioUrl}
                audioId={report.recordings && report.recordings.length > 0 ? report.recordings[report.recordings.length - 1].id : null}
                recordings={report.recordings || []}
                onTimeUpdate={(t) => setCurrentPlaybackTime(t)}
                seekTime={seekTime}
                onSeekHandled={() => setSeekTime(null)}
              />

              {/* Multi-recording History & Add Button */}
              {report.recordings && report.recordings.length > 0 && (
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                    <span className="flex items-center gap-1.5">
                      <Volume2 className="w-3.5 h-3.5 text-teal-600" />
                      Recorded Takes ({report.recordings.length})
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setIsAddingSecondaryRecording(true);
                        startRecording();
                      }}
                      disabled={isRecording}
                      className="text-xs text-teal-600 hover:text-teal-700 font-semibold flex items-center gap-1 cursor-pointer disabled:opacity-50"
                    >
                      <Plus className="w-3 h-3" /> Add Take
                    </button>
                  </div>
                  <div className="space-y-1 max-h-28 overflow-y-auto">
                    {report.recordings.map((rec, rIdx) => (
                      <div
                        key={rec.id}
                        className="p-1.5 bg-white border border-slate-200 rounded flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setSeekTime(0);
                            }}
                            className="p-1 rounded-full bg-teal-50 text-teal-600 hover:bg-teal-100 cursor-pointer"
                            title="Play this take"
                          >
                            <Play className="w-2.5 h-2.5 fill-current" />
                          </button>
                          <span className="font-semibold text-slate-700">Take #{rIdx + 1}</span>
                          {rec.duration_seconds && (
                            <span className="text-[11px] font-mono text-slate-500">
                              ({Math.round(rec.duration_seconds)}s)
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-slate-400">
                          {rec.recorded_at ? new Date(rec.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {transcribing && (
              <div className="p-2.5 bg-teal-50 border border-teal-200 text-teal-800 text-xs rounded-lg flex items-center gap-2 font-medium">
                <Clock className="w-3.5 h-3.5 animate-spin flex-shrink-0 text-teal-600" />
                <span>Transcribing audio on CPU (Whisper INT8)...</span>
              </div>
            )}

            {/* Primary Action Button: Process with AI (Primary Teal) */}
            <button
              type="button"
              onClick={handleGenerateStructuredDraft}
              disabled={structuring || !transcript.trim()}
              className="w-full py-2.5 px-4 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg shadow-xs flex items-center justify-center gap-2 transition cursor-pointer disabled:opacity-50"
            >
              {structuring ? (
                <>
                  <Clock className="w-4 h-4 animate-spin" />
                  <span>Processing with Local AI...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-teal-100" />
                  <span>Process with AI (Generate Draft)</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* ================= RIGHT PANE: CANONICAL STRUCTURED REPORT (7 COLS) ================= */}
        <div className="lg:col-span-7 space-y-4">
          {/* Phase 10D: Anatomical Dictation Checklist */}
          {checklist.length > 0 && (
            <AnatomicalChecklistPanel
              checklist={checklist}
              onSelectOrgan={(key) => {
                const el = document.getElementById(`section-card-${key}`);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }}
            />
          )}

          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-teal-600" />
                <div>
                  <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wider">Structured Findings</h3>
                  <span className="text-[11px] text-slate-500">
                    {isVascular ? 'Hemodynamic tables, perforator cards & clinical narrative' : 'Canonical anatomical findings & institutional presets'}
                  </span>
                </div>
              </div>
              <span className="text-[11px] font-semibold px-2 py-0.5 bg-slate-100 text-slate-700 rounded border border-slate-200">
                {sections.filter((s) => s.is_present).length} of {sections.length} Present
              </span>
            </div>

            {/* Clinical Profile / History Section (if vascular or present) */}
            {(isVascular || report.clinical_profile) && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wide">
                    Clinical Profile / Indication:
                  </label>
                  <span className="text-[10px] text-slate-400">Patient History</span>
                </div>
                <textarea
                  rows={2}
                  value={report.structured_findings?.clinical_profile || report.clinical_profile || ''}
                  onChange={(e) => handleClinicalProfileChange(e.target.value)}
                  placeholder="e.g. Known case of varicose veins, complaints of swelling and heaviness in bilateral lower limbs"
                  className="w-full p-2 bg-white border border-slate-200 rounded text-xs text-slate-800 leading-relaxed focus:outline-none focus:border-teal-500"
                />
              </div>
            )}

            {/* ================= ARTERIAL BIOMETRY TABLE COMPONENT ================= */}
            {isArterial && (
              <div className="p-3.5 bg-white border border-teal-200 rounded-xl space-y-2.5 shadow-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HeartPulse className="w-4 h-4 text-rose-600" />
                    <span className="text-xs font-bold text-slate-900 uppercase tracking-wide">
                      Arterial Doppler Biometry Table ({isUnilateralArterial ? '3-Column Unilateral' : '5-Column Bilateral'})
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddArterialRow}
                    className="flex items-center gap-1 text-[11px] font-semibold text-teal-700 hover:text-teal-800 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Segment
                  </button>
                </div>

                <div className="overflow-x-auto border border-slate-200 rounded-lg">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 text-slate-700 font-bold border-b border-slate-200">
                      {isUnilateralArterial ? (
                        <tr>
                          <th className="p-2">Arterial Segment</th>
                          <th className="p-2 w-28">PSV (cm/s)</th>
                          <th className="p-2 w-40">Flow Pattern</th>
                          <th className="p-2 w-10 text-center">Action</th>
                        </tr>
                      ) : (
                        <tr>
                          <th className="p-2">Arterial Segment</th>
                          <th className="p-2 w-20">Rt PSV</th>
                          <th className="p-2 w-20">Lt PSV</th>
                          <th className="p-2 w-32">Right Flow</th>
                          <th className="p-2 w-32">Left Flow</th>
                          <th className="p-2 w-10 text-center">Action</th>
                        </tr>
                      )}
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {activeArterialTable.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-50/50">
                          <td className="p-1.5 text-slate-800 font-medium">{row.segment_name}</td>
                          {isUnilateralArterial ? (
                            <>
                              <td className="p-1">
                                <input
                                  type="number"
                                  step="0.1"
                                  value={row.psv_right ?? row.psv_left ?? ''}
                                  onChange={(e) =>
                                    handleArterialCellChange(
                                      rIdx,
                                      templateDef?.laterality === 'left' ? 'psv_left' : 'psv_right',
                                      e.target.value ? parseFloat(e.target.value) : null
                                    )
                                  }
                                  placeholder="—"
                                  className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 font-mono focus:outline-none focus:border-teal-500"
                                />
                              </td>
                              <td className="p-1">
                                <select
                                  value={row.flow_pattern_right || row.flow_pattern_left || ''}
                                  onChange={(e) =>
                                    handleArterialCellChange(
                                      rIdx,
                                      templateDef?.laterality === 'left' ? 'flow_pattern_left' : 'flow_pattern_right',
                                      e.target.value || null
                                    )
                                  }
                                  className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                                >
                                  <option value="">[ Blank / Unrecorded ]</option>
                                  <option value="Triphasic">Triphasic</option>
                                  <option value="Biphasic">Biphasic</option>
                                  <option value="Monophasic">Monophasic</option>
                                  <option value="Absent">Absent</option>
                                </select>
                              </td>
                            </>
                          ) : (
                            <>
                              <td className="p-1">
                                <input
                                  type="number"
                                  step="0.1"
                                  value={row.psv_right ?? ''}
                                  onChange={(e) =>
                                    handleArterialCellChange(rIdx, 'psv_right', e.target.value ? parseFloat(e.target.value) : null)
                                  }
                                  placeholder="—"
                                  className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 font-mono focus:outline-none focus:border-teal-500"
                                />
                              </td>
                              <td className="p-1">
                                <input
                                  type="number"
                                  step="0.1"
                                  value={row.psv_left ?? ''}
                                  onChange={(e) =>
                                    handleArterialCellChange(rIdx, 'psv_left', e.target.value ? parseFloat(e.target.value) : null)
                                  }
                                  placeholder="—"
                                  className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 font-mono focus:outline-none focus:border-teal-500"
                                />
                              </td>
                              <td className="p-1">
                                <select
                                  value={row.flow_pattern_right || ''}
                                  onChange={(e) => handleArterialCellChange(rIdx, 'flow_pattern_right', e.target.value || null)}
                                  className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                                >
                                  <option value="">[ Unrecorded ]</option>
                                  <option value="Triphasic">Triphasic</option>
                                  <option value="Biphasic">Biphasic</option>
                                  <option value="Monophasic">Monophasic</option>
                                  <option value="Absent">Absent</option>
                                </select>
                              </td>
                              <td className="p-1">
                                <select
                                  value={row.flow_pattern_left || ''}
                                  onChange={(e) => handleArterialCellChange(rIdx, 'flow_pattern_left', e.target.value || null)}
                                  className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                                >
                                  <option value="">[ Unrecorded ]</option>
                                  <option value="Triphasic">Triphasic</option>
                                  <option value="Biphasic">Biphasic</option>
                                  <option value="Monophasic">Monophasic</option>
                                  <option value="Absent">Absent</option>
                                </select>
                              </td>
                            </>
                          )}
                          <td className="p-1 text-center">
                            <button
                              type="button"
                              onClick={() => handleDeleteArterialRow(rIdx)}
                              className="text-slate-300 hover:text-red-600 p-1 rounded cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ================= VENOUS REPEATABLE PERFORATOR CARDS COMPONENT ================= */}
            {isVenous && (
              <div className="p-3.5 bg-white border border-teal-200 rounded-xl space-y-2.5 shadow-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-teal-600" />
                    <span className="text-xs font-bold text-slate-900 uppercase tracking-wide">
                      Incompetent Venous Perforators ({activePerforators.length} Identified)
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddPerforator}
                    className="flex items-center gap-1 text-[11px] font-semibold text-teal-700 hover:text-teal-800 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Perforator Card
                  </button>
                </div>

                {activePerforators.length === 0 ? (
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-400 text-center">
                    No incompetent perforators recorded. Dictate findings or click "+ Add Perforator Card".
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                    {activePerforators.map((perf, pIdx) => (
                      <div
                        key={pIdx}
                        className="p-3 bg-teal-50/20 border border-teal-200 rounded-lg space-y-2 relative"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-teal-900 flex items-center gap-1">
                            Perforator #{pIdx + 1}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleDeletePerforator(pIdx)}
                            className="text-slate-400 hover:text-red-600 cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <label className="text-[10px] font-bold text-slate-500 uppercase">Laterality</label>
                            <select
                              value={perf.laterality || 'Right'}
                              onChange={(e) =>
                                handleUpdatePerforator(pIdx, {
                                  ...perf,
                                  laterality: e.target.value as any
                                })
                              }
                              className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 focus:outline-none"
                            >
                              <option value="Right">Right</option>
                              <option value="Left">Left</option>
                              <option value="Bilateral">Bilateral</option>
                            </select>
                          </div>

                          <div>
                            <label className="text-[10px] font-bold text-slate-500 uppercase">Diameter (mm)</label>
                            <input
                              type="number"
                              step="0.1"
                              value={perf.diameter_mm ?? ''}
                              onChange={(e) =>
                                handleUpdatePerforator(pIdx, {
                                  ...perf,
                                  diameter_mm: e.target.value ? parseFloat(e.target.value) : null
                                })
                              }
                              placeholder="e.g. 5.2"
                              className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 focus:outline-none"
                            />
                          </div>

                          <div>
                            <label className="text-[10px] font-bold text-slate-500 uppercase">Aspect</label>
                            <select
                              value={perf.aspect || 'Medial'}
                              onChange={(e) =>
                                handleUpdatePerforator(pIdx, {
                                  ...perf,
                                  aspect: e.target.value
                                })
                              }
                              className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 focus:outline-none"
                            >
                              <option value="Medial">Medial</option>
                              <option value="Lateral">Lateral</option>
                              <option value="Posterior">Posterior</option>
                              <option value="Anterior">Anterior</option>
                            </select>
                          </div>

                          <div>
                            <label className="text-[10px] font-bold text-slate-500 uppercase">Distance (cm)</label>
                            <input
                              type="text"
                              value={perf.distance_cm ?? ''}
                              onChange={(e) =>
                                handleUpdatePerforator(pIdx, {
                                  ...perf,
                                  distance_cm: e.target.value
                                })
                              }
                              placeholder="e.g. 5 cm"
                              className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 focus:outline-none"
                            />
                          </div>
                        </div>

                        <div>
                          <label className="text-[10px] font-bold text-slate-500 uppercase">Anatomic Landmark</label>
                          <input
                            type="text"
                            value={perf.landmark || ''}
                            onChange={(e) =>
                              handleUpdatePerforator(pIdx, {
                                ...perf,
                                landmark: e.target.value
                              })
                            }
                            placeholder="e.g. above medial malleolus / below knee"
                            className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-800 focus:outline-none"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Unassigned Findings Alert Panel */}
            {unassigned.length > 0 && (() => {
              const pendingItems = unassigned.filter((u) => !u.is_resolved);
              const resolvedItems = unassigned.filter((u) => u.is_resolved);
              return (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
                  <div className="flex items-center justify-between gap-2 text-xs font-bold text-amber-900">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      <span>Unassigned Clinical Findings ({pendingItems.length} Pending)</span>
                    </div>
                  </div>
                  {assignError && (
                    <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700 font-medium flex items-center justify-between gap-2">
                      <span>{assignError}</span>
                      <button
                        type="button"
                        onClick={() => setAssignError(null)}
                        className="text-red-500 hover:text-red-700 font-bold cursor-pointer"
                      >
                        ×
                      </button>
                    </div>
                  )}
                  {pendingItems.length > 0 && (
                    <div className="space-y-1.5 text-xs">
                      {pendingItems.map((u) => (
                        <div
                          key={u.id}
                          className="p-2 bg-white border border-amber-200 rounded space-y-2"
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div className="text-slate-800 font-medium">"{u.raw_text}"</div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-[11px] text-slate-500">Assign to:</span>
                              <select
                                value=""
                                disabled={assigningId === u.id}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  if (val) handleAssignUnassigned(u.id, val);
                                }}
                                className="px-2 py-1 border border-slate-200 rounded text-xs bg-white text-slate-800 disabled:opacity-50"
                              >
                                <option value="">
                                  {assigningId === u.id ? 'Assigning...' : 'Select section...'}
                                </option>
                                {sections.map((s) => (
                                  <option key={s.key} value={s.key}>
                                    {s.label}
                                  </option>
                                ))}
                                <option value="impression">Impression</option>
                              </select>
                              <button
                                type="button"
                                disabled={assigningId === u.id}
                                onClick={() => {
                                  setExcludingId(excludingId === u.id ? null : u.id);
                                  setExcludeReason('');
                                }}
                                className="px-2 py-1 border border-slate-200 hover:bg-slate-50 rounded text-[11px] font-semibold text-slate-600 cursor-pointer"
                              >
                                Exclude
                              </button>
                            </div>
                          </div>
                          {excludingId === u.id && (
                            <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
                              <input
                                type="text"
                                value={excludeReason}
                                onChange={(e) => setExcludeReason(e.target.value)}
                                placeholder="Document clinical reason for exclusion..."
                                className="flex-1 px-2.5 py-1 border border-slate-200 rounded text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                              />
                              <button
                                type="button"
                                disabled={assigningId === u.id}
                                onClick={() => handleExcludeUnassigned(u.id)}
                                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-900 text-white rounded text-[11px] font-semibold cursor-pointer"
                              >
                                Confirm Exclusion
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {resolvedItems.length > 0 && (
                    <div className="space-y-1 pt-1">
                      {resolvedItems.map((u) => {
                        const targetLabel =
                          u.resolved_organ_key === 'impression'
                            ? 'Impression'
                            : sections.find((s) => s.key === u.resolved_organ_key)?.label || u.resolved_organ_key;
                        return (
                          <div
                            key={u.id}
                            className="px-2.5 py-1.5 bg-emerald-50/80 border border-emerald-200 rounded text-[11px] text-emerald-900 flex items-center justify-between gap-2"
                          >
                            <span className="truncate">"{u.raw_text}"</span>
                            <span className="font-semibold shrink-0">
                              {u.is_excluded
                                ? `Excluded: ${u.exclusion_reason}`
                                : `Assigned to ${targetLabel}`}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Explicit Correction Audit Trail Panel */}
            {superseded.length > 0 && (
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
                <div className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <History className="w-3.5 h-3.5 text-teal-600" />
                  Explicit Correction Audit Trail ({superseded.length})
                </div>
                <div className="divide-y divide-slate-200 text-xs">
                  {superseded.map((sm, idx) => {
                    const secObj = sections.find((s) => s.key === sm.organ_key);
                    const prevMeas = sm.superseded_measurements && sm.superseded_measurements.length > 0
                      ? sm.superseded_measurements[0].raw_str
                      : null;
                    const actMeas = (sm.active_measurements && sm.active_measurements.length > 0
                      ? sm.active_measurements[0].raw_str
                      : null) || (secObj?.measurements && secObj.measurements.length > 0 ? secObj.measurements[0].raw_str : null);
                    const prevDisplay = (prevMeas || sm.superseded_text || '—')
                      .replace(/\s+by\s+|\s+x\s+/gi, ' × ')
                      .replace(/\bcentimeters?\b/gi, 'cm')
                      .replace(/\bmillimeters?\b/gi, 'mm');
                    const actDisplay = (actMeas || sm.active_text || secObj?.text || '—')
                      .replace(/\s+by\s+|\s+x\s+/gi, ' × ')
                      .replace(/\bcentimeters?\b/gi, 'cm')
                      .replace(/\bmillimeters?\b/gi, 'mm');
                    return (
                      <div key={idx} className="py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-slate-600">
                        <div>
                          <span className="font-bold text-slate-900 capitalize">{sm.organ_key.replace(/_/g, ' ')}:</span>{' '}
                          <span className="text-slate-500">Previous value:</span>{' '}
                          <span className="line-through text-red-600 font-mono font-semibold">{prevDisplay}</span>
                          {sm.superseded_text && (
                            <span className="block text-[10px] text-slate-400 mt-0.5 italic">
                              Original clause: "{sm.superseded_text}"
                            </span>
                          )}
                        </div>
                        <div className="font-mono text-teal-700 font-bold bg-teal-50 border border-teal-200 px-2 py-0.5 rounded whitespace-nowrap self-start sm:self-center">
                          Active value: {actDisplay}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Canonical / Protocol Narrative Sections List */}
            <div className="space-y-3 max-h-[580px] overflow-y-auto pr-1">
              {sections.length === 0 ? (
                <div className="py-12 text-center text-slate-400 text-xs space-y-2">
                  <FileText className="w-8 h-8 mx-auto text-slate-300" />
                  <div>Select an action or dictate ultrasound findings on the left to generate structured draft.</div>
                </div>
              ) : (
                sections.map((sec) => (
                  <div
                    key={sec.key}
                    id={`section-card-${sec.key}`}
                    className={`p-3.5 rounded-xl border transition-all ${
                      sec.is_present
                        ? 'bg-white border-slate-200 border-l-4 border-l-teal-600 shadow-xs'
                        : 'bg-slate-50/60 border-slate-200 opacity-75 hover:opacity-100'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-xs text-slate-900">{sec.label}</span>
                        {sec.is_present ? (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 bg-teal-50 text-teal-700 rounded border border-teal-200">
                            Present
                          </span>
                        ) : (
                          <span className="text-[10px] font-medium px-1.5 py-0.5 bg-slate-100 text-slate-400 rounded">
                            Blank / Undictated
                          </span>
                        )}
                        {(sec.source_type || (sec.findings && sec.findings[0]?.source_type)) && (() => {
                          const st = sec.source_type || sec.findings[0]?.source_type || '';
                          return (
                            <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
                              st === 'voice' || st === 'recorded_voice' ? 'bg-blue-100 text-blue-800' :
                              st === 'typed_transcript' ? 'bg-indigo-100 text-indigo-800' :
                              st === 'uploaded_audio' ? 'bg-sky-100 text-sky-800' :
                              st === 'manual' ? 'bg-purple-100 text-purple-800' :
                              st === 'preset' ? 'bg-teal-100 text-teal-800' :
                              st === 'calculation' ? 'bg-amber-100 text-amber-800' :
                              st === 'ocr_verified' ? 'bg-cyan-100 text-cyan-800 border border-cyan-200' :
                              st === 'ocr_manually_corrected' ? 'bg-teal-100 text-teal-800 border border-teal-200' :
                              st === 'ocr_extracted' ? 'bg-sky-100 text-sky-800 border border-sky-200' : 'bg-slate-100 text-slate-800'
                            }`}>
                              {st === 'voice' || st === 'recorded_voice' ? 'Recorded Voice' :
                               st === 'typed_transcript' ? 'Typed Transcript' :
                               st === 'uploaded_audio' ? 'Uploaded Audio' :
                               st === 'manual' ? 'Manual Edit' :
                               st === 'preset' ? (sec.preset_name ? `Preset: ${sec.preset_name}` : 'Preset') :
                               st === 'calculation' ? 'Calculated' :
                               st === 'ocr_verified' ? 'OCR Verified' :
                               st === 'ocr_manually_corrected' ? 'OCR (Edited)' :
                               st === 'ocr_extracted' ? 'OCR Extracted' : st}
                            </span>
                          );
                        })()}
                      </div>

                      <div className="flex items-center gap-1.5">
                        {/* Normal Preset Button */}
                        <button
                          type="button"
                          onClick={() => setActivePresetModalSection(sec)}
                          className="flex items-center gap-1 text-[11px] font-semibold text-teal-700 bg-teal-50 hover:bg-teal-100 border border-teal-200 px-2 py-0.5 rounded cursor-pointer transition"
                          title="Apply institutional normal preset"
                        >
                          <Sparkles className="w-3 h-3 text-teal-600" />
                          Preset
                        </button>

                        {/* Edit Biometry Button */}
                        <button
                          type="button"
                          onClick={() => setActiveBiometryModalSection(sec)}
                          className="flex items-center gap-1 text-[11px] font-semibold text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 px-2 py-0.5 rounded cursor-pointer transition"
                          title="Edit discrete biometry and measurements"
                        >
                          <Edit3 className="w-3 h-3 text-purple-600" />
                          Edit
                        </button>

                        {sec.is_present && (
                          <button
                            type="button"
                            onClick={() => handleClearSection(sec.key)}
                            className="text-[11px] text-slate-400 hover:text-red-600 font-medium cursor-pointer ml-1"
                          >
                            Clear
                          </button>
                        )}
                      </div>
                    </div>

                    <textarea
                      rows={2}
                      value={sec.text || ''}
                      onChange={(e) => handleSectionTextChange(sec.key, e.target.value)}
                      placeholder={`[ Blank — ${sec.label} not explicitly dictated ]`}
                      className={`w-full p-2.5 rounded-lg text-xs leading-relaxed transition-all focus:outline-none focus:border-teal-500 ${
                        sec.is_present
                          ? 'bg-white border border-slate-200 text-slate-900'
                          : 'bg-transparent border border-dashed border-slate-300 text-slate-500'
                      }`}
                    />

                    {/* Calculated Biometry Card */}
                    {sec.calculated_biometry && (
                      <div className="mt-2 p-2.5 bg-amber-50/70 border border-amber-200 rounded-lg space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
                            <Calculator className="w-3.5 h-3.5 text-amber-600" />
                            Calculated Volume:{' '}
                            {sec.calculated_biometry.volume_cc
                              ? `${sec.calculated_biometry.volume_cc} cc`
                              : `${sec.calculated_biometry.calculated_volume_cc} cc`}
                          </span>
                          <button
                            type="button"
                            onClick={handleRecalculateBiometry}
                            className="text-[11px] font-semibold text-amber-800 hover:text-amber-900 flex items-center gap-1 cursor-pointer"
                          >
                            <Calculator className="w-3 h-3" /> Recalculate
                          </button>
                        </div>
                        <div className="text-[11px] text-amber-800 font-mono">
                          Formula: {sec.calculated_biometry.formula}
                        </div>
                        {sec.calculated_biometry.clinical_source && (
                          <div className="text-[10px] text-amber-700 italic">
                            Citation: {sec.calculated_biometry.clinical_source} (Zero diagnostic inference)
                          </div>
                        )}
                      </div>
                    )}

                    {/* Measurement tags */}
                    {sec.measurements && sec.measurements.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {sec.measurements.map((m, mIdx) => (
                          <span
                            key={mIdx}
                            className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-teal-50 text-teal-800 border border-teal-100 flex items-center gap-1"
                          >
                            <span>📏 {m.raw_str}</span>
                            {m.computed_volume_cc ? ` (${m.computed_volume_cc.toFixed(1)} cc)` : ''}
                            {m.audio_timestamp_start !== undefined && m.audio_timestamp_start !== null && (
                              <button
                                type="button"
                                onClick={() => setSeekTime(m.audio_timestamp_start!)}
                                className="inline-flex items-center gap-0.5 text-[9px] font-mono font-bold text-teal-700 bg-teal-100 hover:bg-teal-200 px-1 py-0.2 rounded cursor-pointer transition ml-1"
                                title={`Play audio at ${m.audio_timestamp_start}s`}
                              >
                                <Play className="w-2.5 h-2.5 fill-current" />
                                {Math.floor(m.audio_timestamp_start)}s
                              </button>
                            )}
                            {m.source_type && (
                              <span className={`text-[9px] font-bold uppercase tracking-wider px-1 py-0.2 rounded ml-0.5 ${
                                m.source_type === 'voice' || m.source_type === 'recorded_voice' ? 'bg-blue-100 text-blue-800' :
                                m.source_type === 'typed_transcript' ? 'bg-indigo-100 text-indigo-800' :
                                m.source_type === 'uploaded_audio' ? 'bg-sky-100 text-sky-800' :
                                m.source_type === 'manual' ? 'bg-purple-100 text-purple-800' :
                                m.source_type === 'preset' ? 'bg-teal-100 text-teal-800' :
                                m.source_type === 'calculation' ? 'bg-amber-100 text-amber-800' :
                                m.source_type === 'ocr_verified' ? 'bg-cyan-100 text-cyan-800' :
                                m.source_type === 'ocr_manually_corrected' ? 'bg-teal-100 text-teal-800' :
                                m.source_type === 'ocr_extracted' ? 'bg-sky-100 text-sky-800' : 'bg-slate-100 text-slate-800'
                              }`}>
                                {m.source_type === 'voice' || m.source_type === 'recorded_voice' ? 'Voice' :
                                 m.source_type === 'typed_transcript' ? 'Typed' :
                                 m.source_type === 'uploaded_audio' ? 'Audio' :
                                 m.source_type === 'ocr_verified' ? 'OCR' :
                                 m.source_type === 'ocr_manually_corrected' ? 'OCR (Edit)' : m.source_type}
                              </span>
                            )}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Recommendations / Advice Field (if vascular or present) */}
            {(isVascular || report.recommendations) && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                    Recommendations / Advice:
                  </label>
                  <span className="text-[10px] text-slate-400">Clinical Management</span>
                </div>
                <textarea
                  rows={2}
                  value={report.structured_findings?.recommendations || report.recommendations || ''}
                  onChange={(e) => handleRecommendationsChange(e.target.value)}
                  placeholder="e.g. Clinical correlation suggested. Recommend surgical vascular consultation and compression stockings."
                  className="w-full p-2 bg-white border border-slate-200 rounded text-xs text-slate-800 leading-relaxed focus:outline-none focus:border-teal-500"
                />
              </div>
            )}

            {/* IMPRESSION / CONCLUSION SECTION */}
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  IMPRESSION:
                </label>
                <span className="text-[11px] text-slate-400 italic">
                  Blank if undictated (No normal phrases fabricated)
                </span>
              </div>
              <textarea
                rows={3}
                value={report.impression || ''}
                onChange={(e) => handleImpressionChange(e.target.value)}
                placeholder="Enter clinical impression..."
                className="w-full p-2.5 bg-white border border-slate-200 rounded text-xs font-semibold text-slate-900 leading-relaxed focus:outline-none focus:border-teal-500"
              />
            </div>
          </div>
        </div>
      </div>

      {/* ================= LIVE REPORT PREVIEW MODAL ================= */}
      {isPreviewOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full h-[90vh] flex flex-col border border-slate-200 overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4 text-teal-600" />
                <h3 className="font-bold text-sm text-slate-900">
                  Clinical Ultrasound Report Live Preview (Template Faithful)
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => window.open(api.getReportDocxUrl(report.id), '_blank')}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  DOCX
                </button>
                <button
                  onClick={() => window.open(api.getReportPdfUrl(report.id), '_blank')}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  PDF
                </button>
                <button
                  onClick={() => setIsPreviewOpen(false)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            <iframe
              src={api.getReportPreviewUrl(report.id)}
              className="flex-1 w-full h-full border-none bg-white"
              title="Report Preview"
            />
          </div>
        </div>
      )}

      {/* ================= CLINICIAN REVIEW MODAL ================= */}
      {isReviewModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4 border border-slate-200">
            <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="text-center">
              <h3 className="font-bold text-slate-900 text-base">Radiologist Review & Sign-Off</h3>
              <p className="text-xs text-slate-500 mt-1">
                Verifying this study finalizes findings and removes draft banners from exports.
              </p>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Authenticated Signing Radiologist
              </label>
              <input
                type="text"
                readOnly
                value={reviewerName}
                className="w-full px-3 py-2 border border-slate-200 bg-slate-50 rounded-lg text-sm font-semibold text-slate-800 focus:outline-none"
              />
            </div>

            {unassigned.some((u) => !u.is_resolved) ? (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 space-y-1">
                <div className="font-bold">Clinical Completeness Guard: Sign-Off Blocked</div>
                <div>
                  {unassigned.filter((u) => !u.is_resolved).length} unresolved clinical finding(s) must be assigned to an
                  anatomical section or explicitly excluded with a documented reason before final sign-off.
                </div>
              </div>
            ) : (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                <strong>Notice:</strong> Subsequent edits after sign-off will automatically revert the report back
                to DRAFT status to maintain clinical audit safety.
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsReviewModalOpen(false)}
                className="flex-1 py-2 border border-slate-200 text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={unassigned.some((u) => !u.is_resolved)}
                onClick={handleMarkReviewed}
                className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg cursor-pointer shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Confirm Sign-Off
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================= REVISION AUDIT MODAL ================= */}
      {isRevisionsOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[80vh] flex flex-col border border-slate-200 overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-teal-600" />
                <h3 className="font-bold text-sm text-slate-900">Report Revision History & Audit Trail</h3>
              </div>
              <button
                onClick={() => setIsRevisionsOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-md cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 flex-1 overflow-y-auto space-y-2.5 text-xs">
              {!revisions.length ? (
                <div className="text-center text-slate-400 py-8">No revision history recorded yet.</div>
              ) : (
                revisions.map((rev) => (
                  <div key={rev.id} className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800">
                        Revision #{rev.revision_number} — <span className="uppercase text-teal-600">{rev.change_type}</span>
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(rev.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="text-slate-500 text-[11px]">Changed by: {rev.changed_by}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Phase 10D: Normal Presets Modal */}
      {activePresetModalSection && (
        <NormalPresetsModal
          isOpen={Boolean(activePresetModalSection)}
          onClose={() => setActivePresetModalSection(null)}
          sectionKey={activePresetModalSection.key}
          sectionLabel={activePresetModalSection.label}
          preset={presetsCatalog[activePresetModalSection.key] || null}
          currentText={activePresetModalSection.text}
          onApply={(presetName) => handleApplyPreset(activePresetModalSection.key, presetName)}
          onRemove={() => handleRemovePreset(activePresetModalSection.key)}
        />
      )}

      {/* Phase 10D: Advanced Measurement & Biometry Editor Modal */}
      {activeBiometryModalSection && (
        <AdvancedMeasurementEditorModal
          isOpen={Boolean(activeBiometryModalSection)}
          onClose={() => setActiveBiometryModalSection(null)}
          section={activeBiometryModalSection}
          onSave={handleSaveSectionModal}
        />
      )}

      {/* Phase 10E: Scan Measurements (Local OCR) Modal */}
      {isScanModalOpen && report && (
        <ScanMeasurementsModal
          reportId={report.id}
          isOpen={isScanModalOpen}
          onClose={() => setIsScanModalOpen(false)}
          onMeasurementsConfirmed={() => {
            loadReport();
            setIsDirty(false);
          }}
        />
      )}
    </div>
  );
};
