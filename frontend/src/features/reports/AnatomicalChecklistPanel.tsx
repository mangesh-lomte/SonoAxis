import React, { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, Circle, Edit3, Sparkles, AlertCircle, Keyboard, Upload, Camera } from 'lucide-react';
import type { AnatomicalChecklistItem } from '../../types';

interface AnatomicalChecklistPanelProps {
  checklist: AnatomicalChecklistItem[];
  onSelectOrgan?: (organKey: string) => void;
}

export const AnatomicalChecklistPanel: React.FC<AnatomicalChecklistPanelProps> = ({
  checklist,
  onSelectOrgan,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  const documentedCount = checklist.filter((item) => item.status !== 'not_documented').length;
  const totalCount = checklist.length;

  const getStatusBadge = (status: AnatomicalChecklistItem['status']) => {
    switch (status) {
      case 'dictated':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded">
            <CheckCircle2 className="w-2.5 h-2.5 text-blue-600" />
            Recorded Voice
          </span>
        );
      case 'typed_transcript':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded">
            <Keyboard className="w-2.5 h-2.5 text-indigo-600" />
            Typed
          </span>
        );
      case 'uploaded_audio':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-sky-700 bg-sky-50 border border-sky-200 px-1.5 py-0.5 rounded">
            <Upload className="w-2.5 h-2.5 text-sky-600" />
            Audio File
          </span>
        );
      case 'ocr_verified':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-cyan-700 bg-cyan-50 border border-cyan-200 px-1.5 py-0.5 rounded">
            <Camera className="w-2.5 h-2.5 text-cyan-600" />
            OCR
          </span>
        );
      case 'manually_entered':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-purple-700 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded">
            <Edit3 className="w-2.5 h-2.5 text-purple-600" />
            Manual
          </span>
        );
      case 'preset_applied':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-teal-700 bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded">
            <Sparkles className="w-2.5 h-2.5 text-teal-600" />
            Preset
          </span>
        );
      case 'requires_review':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
            <AlertCircle className="w-2.5 h-2.5 text-amber-600" />
            Review
          </span>
        );
      case 'not_documented':
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-medium text-slate-400 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded">
            <Circle className="w-2 h-2 text-slate-300" />
            Pending
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden mb-4">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50/70 hover:bg-slate-100/70 transition text-left cursor-pointer"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-slate-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-500" />
          )}
          <span className="font-semibold text-xs text-slate-800 uppercase tracking-wider">
            Anatomical Dictation Guidance
          </span>
        </div>
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-semibold text-slate-600">
            {documentedCount} of {totalCount} documented
          </span>
          <div className="w-20 h-2 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-teal-600 transition-all duration-300"
              style={{ width: `${totalCount > 0 ? (documentedCount / totalCount) * 100 : 0}%` }}
            />
          </div>
        </div>
      </button>

      {isExpanded && (
        <div className="p-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 border-t border-slate-100 max-h-60 overflow-y-auto">
          {checklist.map((item) => (
            <div
              key={item.key}
              onClick={() => onSelectOrgan && onSelectOrgan(item.key)}
              className={`p-2.5 rounded-lg border cursor-pointer transition text-left ${
                item.is_present
                  ? 'bg-teal-50/30 border-teal-200 hover:bg-teal-50/60'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between gap-1 mb-1">
                <span className="font-semibold text-xs text-slate-800 truncate" title={item.label}>
                  {item.label}
                </span>
                {getStatusBadge(item.status)}
              </div>
              <p className="text-[11px] text-slate-500 line-clamp-1" title={item.description}>
                {item.summary_text || item.description}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
