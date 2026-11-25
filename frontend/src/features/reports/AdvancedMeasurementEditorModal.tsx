import React, { useState, useEffect } from 'react';
import { X, Save, Edit3, Plus, Trash2 } from 'lucide-react';
import type { ReportSection, MeasurementItem } from '../../types';

interface AdvancedMeasurementEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  section: ReportSection | null;
  onSave: (updatedSection: ReportSection) => Promise<void>;
}

export const AdvancedMeasurementEditorModal: React.FC<AdvancedMeasurementEditorModalProps> = ({
  isOpen,
  onClose,
  section,
  onSave,
}) => {
  const [text, setText] = useState<string>('');
  const [measurements, setMeasurements] = useState<MeasurementItem[]>([]);
  const [saving, setSaving] = useState<boolean>(false);

  useEffect(() => {
    if (section) {
      setText(section.text || '');
      setMeasurements(section.measurements ? JSON.parse(JSON.stringify(section.measurements)) : []);
    }
  }, [section]);

  if (!isOpen || !section) return null;

  const handleUpdateMeasurement = (idx: number, field: string, val: any) => {
    setMeasurements((prev) => {
      const copy = [...prev];
      const target = { ...copy[idx], [field]: val };

      // Update raw_str when values or units change
      if (field === 'val_primary' || field === 'val_secondary' || field === 'val_tertiary' || field === 'unit') {
        const u = field === 'unit' ? val : (target.unit || 'cm');
        const p = field === 'val_primary' ? val : target.val_primary;
        const s = field === 'val_secondary' ? val : target.val_secondary;
        const t = field === 'val_tertiary' ? val : target.val_tertiary;

        if (target.dimension_count === 3 && p && s && t) {
          target.raw_str = `${p} x ${s} x ${t} ${u}`;
          target.value = [p, s, t];
        } else if (target.dimension_count === 2 && p && s) {
          target.raw_str = `${p} x ${s} ${u}`;
          target.value = [p, s];
        } else if (p) {
          target.raw_str = `${p} ${u}`;
          target.value = p;
        }
      }
      target.source_type = 'manual';
      copy[idx] = target;
      return copy;
    });
  };

  const handleAddMeasurement = () => {
    setMeasurements((prev) => [
      ...prev,
      {
        raw_str: '1.0 cm',
        val_primary: 1.0,
        unit: 'cm',
        dimension_count: 1,
        is_volume: false,
        source_type: 'manual',
      },
    ]);
  };

  const handleRemoveMeasurement = (idx: number) => {
    setMeasurements((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const updated: ReportSection = {
        ...section,
        is_present: Boolean(text.trim() || measurements.length > 0),
        text: text.trim() || null,
        measurements: measurements.map((m) => ({ ...m, source_type: 'manual' })),
        source_type: 'manual',
      };
      await onSave(updated);
      onClose();
    } catch (e: any) {
      alert(`Save error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-xl w-full border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-purple-50 border border-purple-200 rounded-lg text-purple-700">
              <Edit3 className="w-4 h-4 text-purple-600" />
            </div>
            <h3 className="font-bold text-slate-800 text-sm">
              Advanced Biometry & Narrative Editor — {section.label}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto space-y-5 flex-1">
          {/* Narrative Text */}
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Section Narrative Description
            </label>
            <textarea
              rows={3}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={`Enter findings for ${section.label}...`}
              className="w-full text-xs text-slate-800 p-2.5 border border-slate-200 rounded-lg focus:outline-none focus:border-teal-500"
            />
          </div>

          {/* Biometry & Measurements */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-700">
                Discrete Measurements & Biometry
              </label>
              <button
                type="button"
                onClick={handleAddMeasurement}
                className="text-xs text-teal-600 hover:text-teal-700 flex items-center gap-1 font-semibold cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Measurement
              </button>
            </div>

            {measurements.length === 0 ? (
              <p className="text-xs text-slate-400 italic bg-slate-50 p-3 rounded-lg border border-slate-200 text-center">
                No discrete measurements associated with this section.
              </p>
            ) : (
              <div className="space-y-3">
                {measurements.map((m, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-slate-700">
                        Measurement #{idx + 1}
                      </span>
                      <div className="flex items-center gap-2">
                        <select
                          value={m.dimension_count || 1}
                          onChange={(e) =>
                            handleUpdateMeasurement(idx, 'dimension_count', parseInt(e.target.value, 10))
                          }
                          className="bg-white border border-slate-200 rounded px-2 py-0.5 text-xs text-slate-700 focus:outline-none"
                        >
                          <option value={1}>1D (Single)</option>
                          <option value={2}>2D (Length x Width)</option>
                          <option value={3}>3D (Length x Width x Height)</option>
                        </select>
                        <button
                          type="button"
                          onClick={() => handleRemoveMeasurement(idx)}
                          className="text-slate-400 hover:text-rose-600 p-1 cursor-pointer"
                          title="Remove measurement"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-4 gap-2">
                      <div>
                        <span className="text-[10px] text-slate-500 block mb-0.5">
                          {m.dimension_count === 3 ? 'Length' : (m.dimension_count === 2 ? 'Length' : 'Value')}
                        </span>
                        <input
                          type="number"
                          step="0.1"
                          value={m.val_primary ?? (m.value?.[0] ?? m.value ?? '')}
                          onChange={(e) =>
                            handleUpdateMeasurement(idx, 'val_primary', parseFloat(e.target.value) || 0)
                          }
                          className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                        />
                      </div>

                      {m.dimension_count >= 2 && (
                        <div>
                          <span className="text-[10px] text-slate-500 block mb-0.5">
                            Width
                          </span>
                          <input
                            type="number"
                            step="0.1"
                            value={m.val_secondary ?? (m.value?.[1] ?? '')}
                            onChange={(e) =>
                              handleUpdateMeasurement(idx, 'val_secondary', parseFloat(e.target.value) || 0)
                            }
                            className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                          />
                        </div>
                      )}

                      {m.dimension_count === 3 && (
                        <div>
                          <span className="text-[10px] text-slate-500 block mb-0.5">
                            Height / AP
                          </span>
                          <input
                            type="number"
                            step="0.1"
                            value={m.val_tertiary ?? (m.value?.[2] ?? '')}
                            onChange={(e) =>
                              handleUpdateMeasurement(idx, 'val_tertiary', parseFloat(e.target.value) || 0)
                            }
                            className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                          />
                        </div>
                      )}

                      <div>
                        <span className="text-[10px] text-slate-500 block mb-0.5">Unit</span>
                        <select
                          value={m.unit || 'cm'}
                          onChange={(e) => handleUpdateMeasurement(idx, 'unit', e.target.value)}
                          className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-800 focus:outline-none focus:border-teal-500"
                        >
                          <option value="cm">cm</option>
                          <option value="mm">mm</option>
                          <option value="cc">cc</option>
                          <option value="cm/s">cm/s</option>
                          <option value="mmHg">mmHg</option>
                        </select>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-slate-100 bg-slate-50">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-200/50 rounded-lg border border-slate-200 transition cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 text-xs font-bold text-white bg-teal-600 hover:bg-teal-500 rounded-lg shadow-xs transition disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};
