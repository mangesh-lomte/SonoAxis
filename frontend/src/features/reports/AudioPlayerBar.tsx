import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, FastForward } from 'lucide-react';

interface AudioPlayerBarProps {
  audioUrl?: string | null;
  audioId?: string | null;
  recordings?: Array<{ id: string; duration_seconds?: number; filename?: string; recorded_at?: string }>;
  onTimeUpdate?: (currentTime: number) => void;
  seekTime?: number | null;
  onSeekHandled?: () => void;
}

export const AudioPlayerBar: React.FC<AudioPlayerBarProps> = ({
  audioUrl,
  audioId,
  recordings = [],
  onTimeUpdate,
  seekTime,
  onSeekHandled,
}) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [playbackRate, setPlaybackRate] = useState<number>(1.0);
  const [selectedAudioId, setSelectedAudioId] = useState<string | null>(audioId || null);

  const activeSrc = selectedAudioId
    ? `/api/audio/${selectedAudioId}`
    : (audioUrl || '');

  useEffect(() => {
    if (audioId) {
      setSelectedAudioId(audioId);
    } else if (recordings.length > 0 && !selectedAudioId) {
      setSelectedAudioId(recordings[recordings.length - 1].id);
    }
  }, [audioId, recordings]);

  // Handle external seek requests (e.g. clicking on finding timestamp badge)
  useEffect(() => {
    if (seekTime !== null && seekTime !== undefined && audioRef.current) {
      audioRef.current.currentTime = seekTime;
      audioRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
      if (onSeekHandled) onSeekHandled();
    }
  }, [seekTime]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => setIsPlaying(true)).catch((e) => console.warn('Play error:', e));
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      const cur = audioRef.current.currentTime;
      setCurrentTime(cur);
      if (onTimeUpdate) {
        onTimeUpdate(cur);
      }
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration || 0);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
      setCurrentTime(val);
      if (onTimeUpdate) onTimeUpdate(val);
    }
  };

  const cycleSpeed = () => {
    const speeds = [0.75, 1.0, 1.25, 1.5];
    const nextIdx = (speeds.indexOf(playbackRate) + 1) % speeds.length;
    const nextRate = speeds[nextIdx];
    setPlaybackRate(nextRate);
    if (audioRef.current) {
      audioRef.current.playbackRate = nextRate;
    }
  };

  const formatTime = (secs: number) => {
    if (isNaN(secs)) return '00:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (!activeSrc) return null;

  return (
    <div className="bg-[#020617] text-slate-100 rounded-xl p-3 shadow-md flex flex-wrap items-center gap-3 border border-slate-800">
      <audio
        ref={audioRef}
        src={activeSrc}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={() => setIsPlaying(false)}
        preload="metadata"
      />

      {/* Multiple Recording Selector */}
      {recordings.length > 1 && (
        <select
          value={selectedAudioId || ''}
          onChange={(e) => {
            setSelectedAudioId(e.target.value);
            setIsPlaying(false);
          }}
          className="bg-slate-900 text-xs text-slate-200 border border-slate-700/80 rounded-md px-2 py-1 focus:ring-1 focus:ring-teal-500 focus:outline-none"
        >
          {recordings.map((r, idx) => (
            <option key={r.id} value={r.id}>
              Take #{idx + 1} {r.duration_seconds ? `(${Math.round(r.duration_seconds)}s)` : ''}
            </option>
          ))}
        </select>
      )}

      {/* Play/Pause Button */}
      <button
        type="button"
        onClick={togglePlay}
        className="w-7 h-7 rounded-full bg-teal-600 hover:bg-teal-500 flex items-center justify-center text-white transition focus:outline-none shadow-xs"
        title={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5 fill-current" />}
      </button>

      {/* Current Position / Duration */}
      <span className="text-[11px] font-mono text-slate-300 min-w-[70px]">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>

      {/* Scrub Slider */}
      <input
        type="range"
        min={0}
        max={duration || 100}
        step={0.1}
        value={currentTime}
        onChange={handleSeek}
        className="flex-1 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-500 focus:outline-none"
      />

      {/* Playback Speed Button */}
      <button
        type="button"
        onClick={cycleSpeed}
        className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-[11px] font-medium text-slate-300 border border-slate-700/80 flex items-center gap-1 transition"
        title="Toggle playback speed (0.75x, 1x, 1.25x, 1.5x)"
      >
        <FastForward className="w-3 h-3 text-slate-400" />
        {playbackRate}x
      </button>

      {/* Synchronized Status Pill */}
      <span className="text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 bg-teal-950 text-teal-300 border border-teal-800/60 rounded">
        Audio Sync
      </span>
    </div>
  );
};
