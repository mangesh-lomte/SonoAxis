/**
 * Local IndexedDB temporary chunk recovery for audio dictation sessions.
 * Protects against accidental browser tab closure, accidental refresh, or network loss.
 * 100% browser-local; zero external transmission.
 */

const DB_NAME = 'sonoaxis_recording_recovery_db';
const DB_VERSION = 1;
const STORE_NAME = 'audio_drafts';

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      reject(new Error('IndexedDB not supported in this browser'));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'reportId' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export interface AudioDraft {
  reportId: string;
  blob: Blob;
  mimeType: string;
  timestamp: number;
  durationSeconds: number;
}

export const recordingRecovery = {
  async saveDraft(reportId: string, blob: Blob, durationSeconds: number): Promise<void> {
    try {
      const db = await openDB();
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const draft: AudioDraft = {
        reportId,
        blob,
        mimeType: blob.type,
        timestamp: Date.now(),
        durationSeconds,
      };
      store.put(draft);
      return new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch (e) {
      console.warn('Failed to save audio draft to IndexedDB:', e);
    }
  },

  async getDraft(reportId: string): Promise<AudioDraft | null> {
    try {
      const db = await openDB();
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.get(reportId);
      return new Promise((resolve, reject) => {
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error);
      });
    } catch (e) {
      console.warn('Failed to load audio draft from IndexedDB:', e);
      return null;
    }
  },

  async clearDraft(reportId: string): Promise<void> {
    try {
      const db = await openDB();
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      store.delete(reportId);
      return new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch (e) {
      console.warn('Failed to clear audio draft from IndexedDB:', e);
    }
  },
};
