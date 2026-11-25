import React, { useState, useRef, useEffect } from 'react';
import {
  X,
  Upload,
  Image as ImageIcon,
  Check,
  AlertTriangle,
  ZoomIn,
  ZoomOut,
  Maximize2,
  FileText,
  ChevronDown,
  ChevronRight,
  Crop,
  Scan,
  ShieldAlert,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import type {
  OCRCandidateMeasurement,
  OCRUploadResponse,
  OCRConfirmationItem,
  OCRConfirmRequest,
  OCRAssignableField,
  OCRRegionBox,
} from '../../types';
import { api } from '../../services/api';

interface ScanMeasurementsModalProps {
  reportId: string;
  isOpen: boolean;
  onClose: () => void;
  onMeasurementsConfirmed: () => void;
}

const FALLBACK_TARGET_FIELDS: OCRAssignableField[] = [
  { field_key: 'liver', section_key: 'liver', label: 'Liver', default_unit: 'cm' },
  { field_key: 'gb_wall', section_key: 'gall_bladder', label: 'Gall Bladder Wall Thickness', default_unit: 'mm' },
  { field_key: 'gall_bladder', section_key: 'gall_bladder', label: 'Gall Bladder', default_unit: 'mm' },
  { field_key: 'cbd', section_key: 'cbd', label: 'Common Bile Duct', default_unit: 'mm' },
  { field_key: 'rk_length', section_key: 'right_kidney', label: 'Right Kidney Length', laterality: 'right', default_unit: 'cm' },
  { field_key: 'rk_ap', section_key: 'right_kidney', label: 'Right Kidney AP Dimension', laterality: 'right', default_unit: 'cm' },
  { field_key: 'right_kidney', section_key: 'right_kidney', label: 'Right Kidney (2D)', laterality: 'right', default_unit: 'cm' },
  { field_key: 'lk_length', section_key: 'left_kidney', label: 'Left Kidney Length', laterality: 'left', default_unit: 'cm' },
  { field_key: 'lk_ap', section_key: 'left_kidney', label: 'Left Kidney AP Dimension', laterality: 'left', default_unit: 'cm' },
  { field_key: 'left_kidney', section_key: 'left_kidney', label: 'Left Kidney (2D)', laterality: 'left', default_unit: 'cm' },
  { field_key: 'spleen', section_key: 'spleen', label: 'Spleen', default_unit: 'cm' },
  { field_key: 'prostate', section_key: 'prostate', label: 'Prostate (3D Dimensions)', default_unit: 'cm' },
  { field_key: 'prostate_volume', section_key: 'prostate', label: 'Prostate Volume', default_unit: 'cc' },
  { field_key: 'pvr', section_key: 'urinary_bladder', label: 'Post Void Residual', default_unit: 'ml' },
  { field_key: 'urinary_bladder', section_key: 'urinary_bladder', label: 'Urinary Bladder', default_unit: 'ml' },
  { field_key: 'pancreas', section_key: 'pancreas', label: 'Pancreas', default_unit: 'mm' },
];

type RectPx = { x1: number; y1: number; x2: number; y2: number };

const mapCandidateOptionValue = (cand: OCRCandidateMeasurement, fields: OCRAssignableField[]): string => {
  if (cand.proposed_destination_field === 'unassigned') return 'unassigned';
  const byLabel = fields.find(
    f => f.label.toLowerCase() === cand.anatomical_label.toLowerCase()
  );
  if (byLabel) return byLabel.field_key;
  const byKey = fields.find(f => f.field_key === cand.proposed_destination_field || f.section_key === cand.proposed_destination_field);
  return byKey ? byKey.field_key : cand.proposed_destination_field;
};

export const ScanMeasurementsModal: React.FC<ScanMeasurementsModalProps> = ({
  reportId,
  isOpen,
  onClose,
  onMeasurementsConfirmed,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [rotateDegrees, setRotateDegrees] = useState<number>(0);
  const [ocrMode, setOcrMode] = useState<'auto' | 'region' | 'full'>('auto');
  const [manualCrop, setManualCrop] = useState<RectPx | null>(null);
  const [naturalDims, setNaturalDims] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null);
  const [isDrawingOnReview, setIsDrawingOnReview] = useState<boolean>(false);

  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Review phase state
  const [ocrResponse, setOcrResponse] = useState<OCRUploadResponse | null>(null);
  const [candidates, setCandidates] = useState<OCRCandidateMeasurement[]>([]);
  const [valueDrafts, setValueDrafts] = useState<Record<string, string>>({});
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [showRawOcr, setShowRawOcr] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewImgRef = useRef<HTMLImageElement>(null);
  const reviewImgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith('image/')) {
          const file = items[i].getAsFile();
          if (file) {
            handleFileSelect(file);
            break;
          }
        }
      }
    };
    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, [isOpen]);

  if (!isOpen) return null;

  const targetFields: OCRAssignableField[] =
    ocrResponse?.available_target_fields && ocrResponse.available_target_fields.length > 0
      ? ocrResponse.available_target_fields
      : FALLBACK_TARGET_FIELDS;

  const handleFileSelect = (file: File) => {
    setErrorMessage(null);
    if (!file.type.startsWith('image/')) {
      setErrorMessage('Please select a valid image file (PNG, JPEG, WebP, BMP, TIFF).');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setErrorMessage('File size exceeds the 15 MB limit.');
      return;
    }
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setRotateDegrees(0);
    setManualCrop(null);
    setOcrResponse(null);
    setCandidates([]);
    setValueDrafts({});
    setShowRawOcr(false);
    setIsDrawingOnReview(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const applyExtractionResponse = (res: OCRUploadResponse) => {
    setOcrResponse(res);
    // Strict safety rule: ALL newly extracted candidates MUST begin as Pending Review ('pending')
    const initialized = res.candidates.map(c => ({
      ...c,
      verification_status: 'pending' as const,
    }));
    setCandidates(initialized);
    const drafts: Record<string, string> = {};
    for (const c of initialized) {
      drafts[c.measurement_id] = Array.isArray(c.value) ? c.value.join(' x ') : String(c.value);
    }
    setValueDrafts(drafts);
    if (initialized.length > 0) {
      setSelectedCandidateId(initialized[0].measurement_id);
    } else {
      setSelectedCandidateId(null);
    }
  };

  const runExtraction = async (modeOverride?: 'auto' | 'region' | 'full', cropOverride?: RectPx | null) => {
    if (!selectedFile) return;
    const activeMode = modeOverride ?? ocrMode;
    const activeCrop = cropOverride !== undefined ? cropOverride : manualCrop;

    if (activeMode === 'region' && !activeCrop) {
      setErrorMessage('Draw a rectangular selection over the measurement table first, or choose Auto / Full Image OCR.');
      return;
    }

    setIsExtracting(true);
    setErrorMessage(null);

    try {
      const fd = new FormData();
      fd.append('file', selectedFile);
      fd.append('rotate', rotateDegrees.toString());
      fd.append('mode', activeMode);
      if (activeMode === 'region' && activeCrop) {
        fd.append('crop_x1', Math.round(activeCrop.x1).toString());
        fd.append('crop_y1', Math.round(activeCrop.y1).toString());
        fd.append('crop_x2', Math.round(activeCrop.x2).toString());
        fd.append('crop_y2', Math.round(activeCrop.y2).toString());
      }

      const res = await api.uploadMachinePrintout(reportId, fd);
      applyExtractionResponse(res);
      setOcrMode(activeMode);
      setIsDrawingOnReview(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to extract measurements from the image.');
    } finally {
      setIsExtracting(false);
    }
  };

  // Interactive rectangular pointer helpers (works cleanly with scaled viewports & zoom)
  const clientPointToImagePx = (
    clientX: number,
    clientY: number,
    imgEl: HTMLImageElement | null,
    imgW: number,
    imgH: number
  ): { x: number; y: number } | null => {
    if (!imgEl || imgW <= 0 || imgH <= 0) return null;
    const rect = imgEl.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    const relX = Math.max(0, Math.min(rect.width, clientX - rect.left));
    const relY = Math.max(0, Math.min(rect.height, clientY - rect.top));
    return {
      x: Math.round((relX / rect.width) * imgW),
      y: Math.round((relY / rect.height) * imgH),
    };
  };

  const startRegionDrag = (
    e: React.MouseEvent,
    imgEl: HTMLImageElement | null,
    imgW: number,
    imgH: number
  ) => {
    const pt = clientPointToImagePx(e.clientX, e.clientY, imgEl, imgW, imgH);
    if (!pt) return;
    e.preventDefault();
    setIsDrawing(true);
    setDrawStart(pt);
    setManualCrop({ x1: pt.x, y1: pt.y, x2: pt.x + 1, y2: pt.y + 1 });
  };

  const moveRegionDrag = (
    e: React.MouseEvent,
    imgEl: HTMLImageElement | null,
    imgW: number,
    imgH: number
  ) => {
    if (!isDrawing || !drawStart) return;
    const pt = clientPointToImagePx(e.clientX, e.clientY, imgEl, imgW, imgH);
    if (!pt) return;
    setManualCrop({
      x1: Math.min(drawStart.x, pt.x),
      y1: Math.min(drawStart.y, pt.y),
      x2: Math.max(drawStart.x, pt.x),
      y2: Math.max(drawStart.y, pt.y),
    });
  };

  const endRegionDrag = (triggerReScanOnReview = false) => {
    if (!isDrawing) return;
    setIsDrawing(false);
    setDrawStart(null);
    if (manualCrop && (manualCrop.x2 - manualCrop.x1 < 18 || manualCrop.y2 - manualCrop.y1 < 18)) {
      setManualCrop(null);
      return;
    }
    if (triggerReScanOnReview && manualCrop) {
      runExtraction('region', manualCrop);
    }
  };

  const updateCandidate = (id: string, updates: Partial<OCRCandidateMeasurement>) => {
    setCandidates(prev => prev.map(c => (c.measurement_id === id ? { ...c, ...updates } : c)));
  };

  const handleFieldAssignmentChange = (cand: OCRCandidateMeasurement, selectedKey: string) => {
    if (selectedKey === 'unassigned') {
      updateCandidate(cand.measurement_id, {
        proposed_destination_field: 'unassigned',
        anatomical_label: 'Unassigned Measurement',
        is_uncertain: true,
        uncertainty_reason: 'Unknown or unconfigured anatomical label — requires manual mapping',
        // Unassigned candidates must never stay approved
        verification_status: cand.verification_status === 'rejected' ? 'rejected' : 'pending',
      });
      return;
    }

    const fieldDef = targetFields.find(f => f.field_key === selectedKey);
    if (!fieldDef) return;

    updateCandidate(cand.measurement_id, {
      proposed_destination_field: fieldDef.field_key,
      anatomical_label: fieldDef.label,
      laterality: fieldDef.laterality ?? cand.laterality,
      is_uncertain: false,
      uncertainty_reason: null,
      mapping_confidence: 1.0,
    });
  };

  const handleApproveAllMapped = () => {
    setCandidates(prev =>
      prev.map(c => {
        if (
          c.verification_status !== 'rejected' &&
          c.proposed_destination_field &&
          c.proposed_destination_field !== 'unassigned' &&
          c.proposed_destination_field !== 'kidneys_ambiguous' &&
          !c.is_uncertain
        ) {
          return { ...c, verification_status: 'approved' };
        }
        return c;
      })
    );
  };

  const pendingCount = candidates.filter(c => c.verification_status === 'pending').length;
  const approvedValidCandidates = candidates.filter(
    c =>
      c.verification_status === 'approved' &&
      c.proposed_destination_field &&
      c.proposed_destination_field !== 'unassigned' &&
      c.proposed_destination_field !== 'kidneys_ambiguous'
  );
  const rejectedCount = candidates.filter(c => c.verification_status === 'rejected').length;
  const unassignedCount = candidates.filter(
    c =>
      c.proposed_destination_field === 'unassigned' ||
      c.proposed_destination_field === 'kidneys_ambiguous'
  ).length;

  const handleConfirmApproved = async () => {
    if (!ocrResponse || approvedValidCandidates.length === 0) return;
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      // Strictly exclude unresolved ('pending'), 'rejected', or 'unassigned' measurements from insertion
      const items: OCRConfirmationItem[] = approvedValidCandidates.map(c => ({
        measurement_id: c.measurement_id,
        destination_field: c.proposed_destination_field,
        anatomical_label: c.anatomical_label,
        value: c.value,
        unit: c.normalized_unit || c.original_unit,
        dimension: c.dimension,
        laterality: c.laterality,
        waveform: c.waveform,
        conflict_resolution: c.has_conflict ? 'use_extracted' : 'use_extracted',
        status: 'approved',
      }));

      const payload: OCRConfirmRequest = {
        source_document_id: ocrResponse.source_document_id,
        items,
      };

      await api.confirmOCRMeasurements(reportId, payload);
      onMeasurementsConfirmed();
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save confirmed measurements.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeRegionOverlay: OCRRegionBox | null =
    isDrawing && manualCrop
      ? { ...manualCrop, confidence: 1, detection_method: 'manual_selection' }
      : ocrResponse?.detected_region ?? null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
      <div className="bg-white border border-slate-200 rounded-xl shadow-2xl w-full max-w-6xl h-[88vh] max-h-[92vh] flex flex-col overflow-hidden text-slate-900">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-teal-50 border border-teal-200 rounded-lg text-teal-700">
              <ImageIcon className="w-4 h-4 text-teal-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                Scan Measurements (Region-Aware Tesseract OCR)
              </h2>
              <p className="text-[11px] text-slate-500">
                100% offline biometry extraction · Spatial table reconstruction · Clinical verification required before insertion
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Scan Measurements modal"
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-lg transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mx-5 mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 min-h-0 overflow-hidden p-5 bg-[#F8FAFC] flex flex-col">
          {!ocrResponse ? (
            /* Upload & Optional Manual Region Selection Step */
            <div className="flex flex-col md:flex-row gap-5 flex-1 min-h-0">
              {/* Preview / Dropzone / Region Canvas */}
              <div
                onDragOver={e => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => {
                  if (!selectedFile) fileInputRef.current?.click();
                }}
                className={`flex-1 border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-4 transition ${
                  selectedFile
                    ? 'border-slate-700 bg-[#020617]'
                    : 'border-slate-300 hover:border-teal-500 bg-white cursor-pointer'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={e => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                  accept="image/png,image/jpeg,image/webp,image/bmp,image/tiff"
                  className="hidden"
                />

                {previewUrl ? (
                  <div className="flex flex-col items-center justify-center w-full h-full min-h-0 gap-2">
                    {ocrMode === 'region' && (
                      <div className="text-[11px] text-teal-300 bg-slate-900/90 border border-teal-500/40 px-3 py-1 rounded-full">
                        Drag a rectangle directly over the measurement table ({manualCrop ? `${manualCrop.x2 - manualCrop.x1}×${manualCrop.y2 - manualCrop.y1} px` : 'no region selected yet'})
                      </div>
                    )}
                    <div
                      className={`relative inline-block max-w-full max-h-[430px] overflow-hidden select-none ${
                        ocrMode === 'region' ? 'cursor-crosshair' : ''
                      }`}
                      onMouseDown={e =>
                        ocrMode === 'region' && startRegionDrag(e, previewImgRef.current, naturalDims.w, naturalDims.h)
                      }
                      onMouseMove={e =>
                        ocrMode === 'region' && moveRegionDrag(e, previewImgRef.current, naturalDims.w, naturalDims.h)
                      }
                      onMouseUp={() => ocrMode === 'region' && endRegionDrag(false)}
                      onMouseLeave={() => ocrMode === 'region' && isDrawing && endRegionDrag(false)}
                    >
                      <img
                        ref={previewImgRef}
                        src={previewUrl}
                        alt="Worksheet Preview"
                        draggable={false}
                        onLoad={e => {
                          const im = e.currentTarget;
                          setNaturalDims({ w: im.naturalWidth, h: im.naturalHeight });
                        }}
                        style={{ transform: `rotate(${rotateDegrees}deg)` }}
                        className="max-h-[420px] max-w-full object-contain rounded-lg border border-slate-800 shadow-md block"
                      />
                      {ocrMode === 'region' && manualCrop && naturalDims.w > 0 && (
                        <div
                          style={{
                            left: `${(manualCrop.x1 / naturalDims.w) * 100}%`,
                            top: `${(manualCrop.y1 / naturalDims.h) * 100}%`,
                            width: `${((manualCrop.x2 - manualCrop.x1) / naturalDims.w) * 100}%`,
                            height: `${((manualCrop.y2 - manualCrop.y1) / naturalDims.h) * 100}%`,
                          }}
                          className="absolute border-2 border-teal-400 bg-teal-400/20 pointer-events-none"
                        />
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-slate-400">
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="text-teal-400 hover:text-teal-300 underline cursor-pointer"
                      >
                        Choose Different Image
                      </button>
                      {manualCrop && (
                        <button
                          type="button"
                          onClick={() => setManualCrop(null)}
                          className="text-amber-300 hover:text-amber-200 underline cursor-pointer"
                        >
                          Clear Region
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center space-y-2.5">
                    <div className="mx-auto w-11 h-11 bg-teal-50 border border-teal-200 rounded-full flex items-center justify-center text-teal-600">
                      <Upload className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-800">
                        Drag and drop ultrasound machine printout here, or click to browse
                      </p>
                      <p className="text-[11px] text-slate-500 mt-1">
                        Supports JPEG, PNG, screenshots · Clipboard paste (Ctrl+V) enabled
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Controls Panel */}
              <div className="w-full md:w-80 flex flex-col justify-between bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                <div className="space-y-4">
                  <h3 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    Extraction Mode &amp; Region
                  </h3>

                  {selectedFile && (
                    <div className="space-y-1 text-xs text-slate-700 bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                      <div className="flex justify-between">
                        <span className="text-slate-500">File:</span>
                        <span className="font-mono text-slate-900 truncate max-w-[165px]">{selectedFile.name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Size:</span>
                        <span className="font-mono">{(selectedFile.size / 1024).toFixed(1)} KB</span>
                      </div>
                    </div>
                  )}

                  {/* Extraction Mode Options */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700 block">OCR Region Scope</label>
                    <div className="space-y-1.5">
                      {[
                        {
                          id: 'auto' as const,
                          label: 'Auto Worksheet Region',
                          desc: 'Automatically locates table grid & removes borders',
                        },
                        {
                          id: 'region' as const,
                          label: 'Manual Region Selection',
                          desc: 'Drag a rectangle over only the measurement table',
                        },
                        {
                          id: 'full' as const,
                          label: 'Full Image OCR',
                          desc: 'Scans full screen with caliper duplicate filtering',
                        },
                      ].map(opt => (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => {
                            setOcrMode(opt.id);
                            setErrorMessage(null);
                          }}
                          className={`w-full text-left p-2 rounded-lg border transition cursor-pointer ${
                            ocrMode === opt.id
                              ? 'bg-teal-50/70 border-teal-500 text-teal-900'
                              : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                          }`}
                        >
                          <div className="text-xs font-bold">{opt.label}</div>
                          <div className="text-[10px] text-slate-500">{opt.desc}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700 block">Rotation Correction</label>
                    <div className="grid grid-cols-4 gap-1.5">
                      {[0, 90, 180, 270].map(deg => (
                        <button
                          key={deg}
                          type="button"
                          onClick={() => {
                            setRotateDegrees(deg);
                            setManualCrop(null);
                          }}
                          className={`py-1.5 px-2 text-xs rounded-lg border transition cursor-pointer ${
                            rotateDegrees === deg
                              ? 'bg-teal-50 border-teal-500 text-teal-800 font-bold'
                              : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                          }`}
                        >
                          {deg}°
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100 flex flex-col gap-2">
                  <button
                    type="button"
                    disabled={!selectedFile || isExtracting || (ocrMode === 'region' && !manualCrop)}
                    onClick={() => runExtraction()}
                    className="w-full py-2.5 px-4 bg-teal-600 hover:bg-teal-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-bold text-xs rounded-lg transition flex items-center justify-center gap-2 cursor-pointer shadow-xs"
                  >
                    {isExtracting ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Running Local Tesseract OCR...</span>
                      </>
                    ) : (
                      <>
                        <FileText className="w-3.5 h-3.5" />
                        <span>
                          {ocrMode === 'region' ? 'Extract Selected Region' : 'Extract Measurements'}
                        </span>
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    className="w-full py-1.5 px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg border border-slate-200 transition cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Side-by-Side Clinical Review & Verification Workspace */
            <div className="flex flex-col md:flex-row gap-5 flex-1 min-h-0 overflow-hidden">
              {/* Left Panel: Machine Printout Viewport + Region Selector */}
              <div className="w-full md:w-1/2 flex flex-col min-h-0 bg-[#020617] border border-slate-800 rounded-xl overflow-hidden shadow-xs">
                <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 border-b border-slate-800 bg-[#0F172A] text-xs text-slate-300">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={isExtracting}
                      onClick={() => setIsDrawingOnReview(prev => !prev)}
                      className={`px-2 py-1 rounded text-[11px] font-semibold flex items-center gap-1 border transition cursor-pointer ${
                        isDrawingOnReview
                          ? 'bg-teal-600 border-teal-400 text-white'
                          : 'bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700'
                      }`}
                      title="Drag a custom rectangular region on the image and re-run OCR"
                    >
                      <Crop className="w-3 h-3" />
                      <span>{isDrawingOnReview ? 'Drag Box on Image...' : 'Select Region'}</span>
                    </button>
                    <button
                      type="button"
                      disabled={isExtracting}
                      onClick={() => {
                        setManualCrop(null);
                        runExtraction('auto', null);
                      }}
                      className={`px-2 py-1 rounded text-[11px] font-semibold border transition cursor-pointer ${
                        ocrResponse.ocr_mode_used === 'auto_table_region'
                          ? 'bg-emerald-900/60 border-emerald-500/60 text-emerald-200'
                          : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      Auto Region
                    </button>
                    <button
                      type="button"
                      disabled={isExtracting}
                      onClick={() => {
                        setManualCrop(null);
                        runExtraction('full', null);
                      }}
                      className={`px-2 py-1 rounded text-[11px] font-semibold flex items-center gap-1 border transition cursor-pointer ${
                        ocrResponse.ocr_mode_used === 'full_image'
                          ? 'bg-sky-900/60 border-sky-500/60 text-sky-200'
                          : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      <Scan className="w-3 h-3" />
                      <span>Full Image</span>
                    </button>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setZoomLevel(prev => Math.max(0.6, prev - 0.2))}
                      className="p-1 hover:bg-slate-800 rounded text-slate-300 cursor-pointer"
                      title="Zoom Out"
                    >
                      <ZoomOut className="w-3.5 h-3.5" />
                    </button>
                    <span className="w-9 text-center text-[11px] font-mono">{(zoomLevel * 100).toFixed(0)}%</span>
                    <button
                      type="button"
                      onClick={() => setZoomLevel(prev => Math.min(2.5, prev + 0.2))}
                      className="p-1 hover:bg-slate-800 rounded text-slate-300 cursor-pointer"
                      title="Zoom In"
                    >
                      <ZoomIn className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setZoomLevel(1.0)}
                      className="p-1 hover:bg-slate-800 rounded text-slate-300 cursor-pointer"
                      title="Reset Zoom"
                    >
                      <Maximize2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div className="flex-1 min-h-0 overflow-auto p-4 flex items-center justify-center relative">
                  <div
                    style={{
                      transform: `scale(${zoomLevel})`,
                      transformOrigin: 'center center',
                      transition: 'transform 0.15s ease-out',
                    }}
                    onMouseDown={e =>
                      isDrawingOnReview &&
                      startRegionDrag(e, reviewImgRef.current, ocrResponse.image_width, ocrResponse.image_height)
                    }
                    onMouseMove={e =>
                      isDrawingOnReview &&
                      moveRegionDrag(e, reviewImgRef.current, ocrResponse.image_width, ocrResponse.image_height)
                    }
                    onMouseUp={() => isDrawingOnReview && endRegionDrag(true)}
                    className={`relative inline-block max-w-full select-none ${
                      isDrawingOnReview ? 'cursor-crosshair' : ''
                    }`}
                  >
                    <img
                      ref={reviewImgRef}
                      src={ocrResponse.image_url}
                      alt="Source Machine Printout"
                      draggable={false}
                      className="max-h-full max-w-full object-contain rounded border border-slate-800 block"
                    />

                    {/* Active Worksheet / Manual Region Frame */}
                    {activeRegionOverlay && (
                      <div
                        style={{
                          left: `${(activeRegionOverlay.x1 / ocrResponse.image_width) * 100}%`,
                          top: `${(activeRegionOverlay.y1 / ocrResponse.image_height) * 100}%`,
                          width: `${((activeRegionOverlay.x2 - activeRegionOverlay.x1) / ocrResponse.image_width) * 100}%`,
                          height: `${((activeRegionOverlay.y2 - activeRegionOverlay.y1) / ocrResponse.image_height) * 100}%`,
                        }}
                        className="absolute border-2 border-dashed border-emerald-400/80 bg-emerald-400/5 pointer-events-none"
                      />
                    )}

                    {/* Extracted Candidate Bounding Boxes */}
                    {!isDrawingOnReview &&
                      candidates.map(cand => {
                        if (!cand.bounding_box) return null;
                        const isSelected = cand.measurement_id === selectedCandidateId;
                        const colorCls =
                          cand.verification_status === 'approved'
                            ? 'border-emerald-400 bg-emerald-400/20'
                            : cand.verification_status === 'rejected'
                              ? 'border-rose-400/70 bg-rose-400/10'
                              : isSelected
                                ? 'border-teal-400 bg-teal-400/20'
                                : 'border-amber-400/80 bg-amber-400/10 hover:border-amber-300';

                        return (
                          <div
                            key={cand.measurement_id}
                            onClick={() => setSelectedCandidateId(cand.measurement_id)}
                            style={{
                              left: `${(cand.bounding_box.x / ocrResponse.image_width) * 100}%`,
                              top: `${(cand.bounding_box.y / ocrResponse.image_height) * 100}%`,
                              width: `${(cand.bounding_box.width / ocrResponse.image_width) * 100}%`,
                              height: `${(cand.bounding_box.height / ocrResponse.image_height) * 100}%`,
                            }}
                            className={`absolute border-2 transition cursor-pointer ${colorCls}`}
                            title={`${cand.anatomical_label}: ${cand.raw_text}`}
                          />
                        );
                      })}
                  </div>
                </div>

                <div className="px-4 py-2 border-t border-slate-800 bg-[#0F172A] text-[11px] text-slate-400 flex flex-wrap items-center justify-between gap-2">
                  <span>
                    {ocrResponse.ocr_mode_used === 'auto_table_region'
                      ? 'Auto Worksheet Region'
                      : ocrResponse.ocr_mode_used === 'manual_region'
                        ? 'Manual Selected Region'
                        : 'Full Image OCR'}{' '}
                    · {ocrResponse.execution_time_ms} ms
                  </span>
                  <span>
                    {candidates.length} candidate(s)
                    {ocrResponse.filtered_duplicate_count ? ` · ${ocrResponse.filtered_duplicate_count} annotation duplicate(s) filtered` : ''}
                  </span>
                </div>
              </div>

              {/* Right Panel: Strict Pending Review Verification List */}
              <div className="w-full md:w-1/2 flex flex-col min-h-0 justify-between overflow-hidden bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                {/* Verification Status Bar & Bulk Action */}
                <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold">
                    <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                      Pending Review: {pendingCount}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                      Approved: {approvedValidCandidates.length}
                    </span>
                    {rejectedCount > 0 && (
                      <span className="px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
                        Rejected: {rejectedCount}
                      </span>
                    )}
                    {unassignedCount > 0 && (
                      <span className="px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-200">
                        Unassigned: {unassignedCount}
                      </span>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={handleApproveAllMapped}
                    disabled={candidates.length === 0}
                    className="px-2.5 py-1 text-[11px] font-bold bg-teal-50 text-teal-800 hover:bg-teal-100 border border-teal-200 rounded-lg transition cursor-pointer disabled:opacity-40"
                    title="Approves only confidently mapped measurements; leaves unassigned or uncertain entries Pending Review"
                  >
                    Approve All Valid Mapped
                  </button>
                </div>

                {/* Raw OCR Collapsible Inspector */}
                {ocrResponse.raw_ocr_text && (
                  <div className="mb-2.5 border border-slate-200 rounded-lg overflow-hidden bg-slate-50 shrink-0">
                    <button
                      type="button"
                      onClick={() => setShowRawOcr(!showRawOcr)}
                      className="w-full px-3 py-1.5 flex items-center justify-between text-[11px] font-semibold text-slate-700 hover:bg-slate-100 transition cursor-pointer"
                    >
                      <span className="flex items-center gap-1.5">
                        {showRawOcr ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                        Raw Tesseract OCR Text
                      </span>
                      <span className="font-mono text-[10px] text-slate-500">
                        {ocrResponse.raw_ocr_text.split('\n').length} lines
                      </span>
                    </button>
                    {showRawOcr && (
                      <pre className="p-2.5 text-[10px] font-mono text-slate-700 bg-white border-t border-slate-200 max-h-24 overflow-y-auto whitespace-pre-wrap">
                        {ocrResponse.raw_ocr_text}
                      </pre>
                    )}
                  </div>
                )}

                <div className="overflow-y-auto pr-1 space-y-2.5 flex-1">
                  {candidates.length === 0 ? (
                    <div className="py-12 text-center text-xs text-slate-500">
                      No structured measurement candidates matched in this region. Try adjusting the selection or switching to Full Image OCR.
                    </div>
                  ) : (
                    candidates.map((cand, idx) => {
                      const isSelected = cand.measurement_id === selectedCandidateId;
                      const isUnassigned =
                        !cand.proposed_destination_field ||
                        cand.proposed_destination_field === 'unassigned' ||
                        cand.proposed_destination_field === 'kidneys_ambiguous';
                      const status = cand.verification_status;
                      const currentFieldKey = mapCandidateOptionValue(cand, targetFields);

                      return (
                        <div
                          key={cand.measurement_id}
                          onClick={() => setSelectedCandidateId(cand.measurement_id)}
                          className={`p-3 rounded-xl border transition cursor-pointer ${
                            isSelected
                              ? 'border-teal-500 bg-teal-50/15 shadow-xs'
                              : 'border-slate-200 bg-white hover:border-slate-300'
                          } ${status === 'rejected' ? 'opacity-60 bg-slate-50' : ''}`}
                        >
                          {/* Candidate Header */}
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <div className="flex items-center flex-wrap gap-1.5">
                              <span className="text-[11px] font-mono text-slate-400 font-bold">#{idx + 1}</span>
                              <span className="text-xs font-bold text-slate-900">{cand.anatomical_label}</span>
                              {cand.laterality && (
                                <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 border border-slate-200 rounded text-slate-600 font-mono capitalize">
                                  {cand.laterality}
                                </span>
                              )}
                            </div>

                            <span
                              className={`text-[10px] px-2 py-0.5 rounded-full font-bold border uppercase tracking-wider shrink-0 ${
                                status === 'approved'
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : status === 'rejected'
                                    ? 'bg-rose-50 text-rose-700 border-rose-200'
                                    : 'bg-amber-50 text-amber-800 border-amber-200'
                              }`}
                            >
                              {status === 'approved'
                                ? 'Approved'
                                : status === 'rejected'
                                  ? 'Rejected'
                                  : 'Pending Review'}
                            </span>
                          </div>

                          {/* Raw OCR Line */}
                          <div className="text-[11px] text-slate-600 font-mono bg-slate-50 px-2 py-1 rounded border border-slate-200 mb-2">
                            {cand.raw_text}
                          </div>

                          {/* Explicit Anatomical Field Assignment + Value + Unit Controls */}
                          <div className="grid grid-cols-12 gap-2 mb-2">
                            <div className="col-span-5">
                              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-0.5">
                                Anatomical Field
                              </label>
                              <select
                                aria-label={`Anatomical field for candidate ${idx + 1}`}
                                value={currentFieldKey}
                                onChange={e => handleFieldAssignmentChange(cand, e.target.value)}
                                className={`w-full border rounded px-2 py-1 text-xs focus:outline-none focus:border-teal-500 ${
                                  isUnassigned
                                    ? 'bg-red-50 border-red-300 text-red-800 font-semibold'
                                    : 'bg-white border-slate-200 text-slate-900'
                                }`}
                              >
                                <option value="unassigned">Unassigned (Select field)</option>
                                {targetFields.map(tf => (
                                  <option key={tf.field_key} value={tf.field_key}>
                                    {tf.label}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="col-span-4">
                              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-0.5">
                                Value
                              </label>
                              <input
                                type="text"
                                aria-label={`Value for ${cand.anatomical_label}`}
                                value={valueDrafts[cand.measurement_id] ?? (Array.isArray(cand.value) ? cand.value.join(' x ') : cand.value)}
                                onChange={e => {
                                  const raw = e.target.value;
                                  setValueDrafts(prev => ({ ...prev, [cand.measurement_id]: raw }));
                                  if (/[x×]/.test(raw)) {
                                    const parts = raw
                                      .split(/[x×]/i)
                                      .map(p => parseFloat(p.trim()))
                                      .filter(n => !isNaN(n));
                                    if (parts.length >= 2) {
                                      updateCandidate(cand.measurement_id, { value: parts, dimension: parts.length });
                                    }
                                  } else {
                                    const num = parseFloat(raw);
                                    if (!isNaN(num)) {
                                      updateCandidate(cand.measurement_id, { value: num, dimension: 1 });
                                    }
                                  }
                                }}
                                className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-900 font-mono focus:outline-none focus:border-teal-500"
                              />
                            </div>
                            <div className="col-span-3">
                              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-0.5">
                                Unit
                              </label>
                              <select
                                aria-label={`Unit for ${cand.anatomical_label}`}
                                value={cand.normalized_unit}
                                onChange={e => updateCandidate(cand.measurement_id, { normalized_unit: e.target.value })}
                                className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-900 focus:outline-none focus:border-teal-500"
                              >
                                <option value="cm">cm</option>
                                <option value="mm">mm</option>
                                <option value="cm/s">cm/s</option>
                                <option value="m/s">m/s</option>
                                <option value="cc">cc</option>
                                <option value="ml">ml</option>
                                <option value="mmHg">mmHg</option>
                              </select>
                            </div>
                          </div>

                          {/* Individual Approve / Reject Buttons */}
                          <div className="flex items-center justify-between gap-2 pt-1">
                            <div className="text-[10px] text-slate-500">
                              {isUnassigned ? (
                                <span className="text-red-600 font-semibold">
                                  Assign an anatomical field to enable approval
                                </span>
                              ) : status === 'pending' ? (
                                <span>Awaiting clinician verification</span>
                              ) : status === 'approved' ? (
                                <span className="text-emerald-700 font-semibold">Ready for insertion</span>
                              ) : (
                                <span className="text-rose-700">Excluded from insertion</span>
                              )}
                            </div>
                            <div className="flex items-center gap-1.5">
                              <button
                                type="button"
                                disabled={isUnassigned}
                                onClick={e => {
                                  e.stopPropagation();
                                  updateCandidate(cand.measurement_id, { verification_status: 'approved' });
                                }}
                                className={`px-2.5 py-1 rounded text-[11px] font-semibold border flex items-center gap-1 transition ${
                                  isUnassigned
                                    ? 'bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed'
                                    : status === 'approved'
                                      ? 'bg-emerald-600 border-emerald-600 text-white cursor-pointer'
                                      : 'bg-white border-slate-200 text-emerald-700 hover:bg-emerald-50 cursor-pointer'
                                }`}
                              >
                                <CheckCircle2 className="w-3 h-3" />
                                <span>Approve</span>
                              </button>
                              <button
                                type="button"
                                onClick={e => {
                                  e.stopPropagation();
                                  updateCandidate(cand.measurement_id, { verification_status: 'rejected' });
                                }}
                                className={`px-2.5 py-1 rounded text-[11px] font-semibold border flex items-center gap-1 transition cursor-pointer ${
                                  status === 'rejected'
                                    ? 'bg-rose-600 border-rose-600 text-white'
                                    : 'bg-white border-slate-200 text-rose-700 hover:bg-rose-50'
                                }`}
                              >
                                <XCircle className="w-3 h-3" />
                                <span>Reject</span>
                              </button>
                            </div>
                          </div>

                          {/* Uncertainty Warning */}
                          {cand.is_uncertain && (
                            <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 text-[11px] flex items-center gap-1.5">
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                              <span>{cand.uncertainty_reason}</span>
                            </div>
                          )}

                          {/* Conflict Resolution Box */}
                          {cand.has_conflict && (
                            <div className="mt-2 p-2.5 bg-red-50/70 border border-red-200 rounded-lg text-xs space-y-2">
                              <div className="flex items-center gap-1.5 text-red-800 font-bold text-[11px]">
                                <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                                <span>Conflict with Existing Report Value</span>
                              </div>
                              <div className="grid grid-cols-2 gap-2">
                                <div className="bg-white p-2 rounded border border-slate-200">
                                  <span className="text-slate-500 block text-[10px] font-semibold">Current Value:</span>
                                  <span className="font-mono text-amber-700 font-bold text-xs">
                                    {Array.isArray(cand.existing_value)
                                      ? cand.existing_value.join(' × ')
                                      : cand.existing_value}
                                  </span>
                                </div>
                                <div className="bg-white p-2 rounded border border-slate-200">
                                  <span className="text-slate-500 block text-[10px] font-semibold">OCR Value:</span>
                                  <span className="font-mono text-teal-700 font-bold text-xs">
                                    {Array.isArray(cand.value) ? cand.value.join(' × ') : cand.value} {cand.normalized_unit}
                                  </span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Bottom Confirmation Footer */}
                <div className="pt-3 mt-3 border-t border-slate-200 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setOcrResponse(null);
                        setCandidates([]);
                        setManualCrop(null);
                      }}
                      className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition cursor-pointer"
                    >
                      ← Scan Another Image
                    </button>
                    {(pendingCount > 0 || unassignedCount > 0) && (
                      <span className="text-[10px] text-amber-700 flex items-center gap-1">
                        <ShieldAlert className="w-3.5 h-3.5" />
                        <span>{pendingCount} pending/unresolved excluded</span>
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={onClose}
                      className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 border border-slate-200 rounded-lg transition cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={isSubmitting || approvedValidCandidates.length === 0}
                      onClick={handleConfirmApproved}
                      className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-bold text-xs rounded-lg transition shadow-xs flex items-center gap-1.5 cursor-pointer"
                    >
                      {isSubmitting ? (
                        <>
                          <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          <span>Saving...</span>
                        </>
                      ) : (
                        <>
                          <Check className="w-3.5 h-3.5" />
                          <span>Confirm &amp; Insert ({approvedValidCandidates.length} Approved)</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
