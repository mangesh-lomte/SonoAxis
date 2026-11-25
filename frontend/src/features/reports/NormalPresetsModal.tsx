import React, { useState } from 'react';
import { X, Sparkles, Check, AlertCircle } from 'lucide-react';
import type { PresetItem } from '../../types';

interface NormalPresetsModalProps {
  isOpen: boolean;
  onClose: () => void;
  sectionKey: string;
  sectionLabel: string;
  preset: PresetItem | null;
  currentText: string | null;
  onApply: (presetName: string) => Promise<void>;
  onRemove?: () => Promise<void>;
}

export const NormalPresetsModal: React.FC<NormalPresetsModalProps> = ({
  isOpen,
  onClose,
  sectionLabel,
  preset,
  currentText,
  onApply,
  onRemove,
}) => {
  const [applying, setApplying] = useState<boolean>(false);
  const [removing, setRemoving] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleApply = async () => {
    if (!preset) return;
    try {
      setApplying(true);
      await onApply(preset.name);
      onClose();
    } catch (e: any) {
      alert(`Error applying preset: ${e.message}`);
    } finally {
      setApplying(false);
    }
  };

  const handleRemove = async () => {
    if (!onRemove) return;
    try {
      setRemoving(true);
      await onRemove();
      onClose();
    } catch (e: any) {
      alert(`Error removing preset: ${e.message}`);
    } finally {
      setRemoving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full border border-slate-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-teal-50 border border-teal-200 rounded-lg text-teal-700">
              <Sparkles className="w-4 h-4 text-teal-600" />
            </div>
            <h3 className="font-bold text-slate-800 text-sm">
              Institutional Normal Preset — {sectionLabel}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {preset ? (
            <>
              <div>
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1.5">
                  Institutional Standard Normal Phrasing
                </span>
                <div className="p-3 bg-teal-50/40 border border-teal-200 rounded-lg text-slate-800 text-xs leading-relaxed">
                  {preset.text}
                </div>
              </div>

              <div>
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                  Clinical Rationale
                </span>
                <p className="text-xs text-slate-600 italic">
                  {preset.clinical_rationale}
                </p>
              </div>

              {currentText && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <p className="text-xs text-amber-800">
                    Applying this preset will overwrite current findings for {sectionLabel}. You can remove or modify it at any time.
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="p-4 text-center text-slate-500 text-xs">
              No institutional normal preset configured for section "{sectionLabel}".
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 bg-slate-50">
          {onRemove && currentText ? (
            <button
              type="button"
              onClick={handleRemove}
              disabled={removing || applying}
              className="px-3 py-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 rounded-lg border border-rose-200 transition disabled:opacity-50 cursor-pointer"
            >
              {removing ? 'Removing...' : 'Remove Preset / Clear'}
            </button>
          ) : <div />}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-200/50 rounded-lg border border-slate-200 transition cursor-pointer"
            >
              Cancel
            </button>
            {preset && (
              <button
                type="button"
                onClick={handleApply}
                disabled={applying || removing}
                className="px-4 py-1.5 text-xs font-bold text-white bg-teal-600 hover:bg-teal-500 rounded-lg shadow-xs transition disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
              >
                <Check className="w-3.5 h-3.5" />
                {applying ? 'Applying...' : 'Apply Preset'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
