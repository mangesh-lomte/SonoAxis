import React, { useEffect, useState } from 'react';
import {
  Cpu,
  Database,
  FileCheck,
  HardDrive,
  CheckCircle2,
  AlertCircle,
  UserCheck,
  KeyRound,
  Users,
  UserPlus,
  Shield,
} from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import type { EngineStatus, ExportStatus, DoctorUser, DoctorRole } from '../../types';

export const SettingsPage: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const isAdmin = user?.role === 'Administrator';

  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [exportStatus, setExportStatus] = useState<ExportStatus | null>(null);
  const [backups, setBackups] = useState<any[]>([]);
  const [teamUsers, setTeamUsers] = useState<DoctorUser[]>([]);
  const [backupLoading, setBackupLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Authenticated profile form
  const [profileForm, setProfileForm] = useState({
    full_name: user?.full_name || '',
    credentials: user?.credentials || '',
    designation: user?.designation || '',
    department: user?.department || '',
    email: user?.email || '',
  });
  const [savingProfile, setSavingProfile] = useState<boolean>(false);

  // Password change form
  const [pwForm, setPwForm] = useState({ current_password: '', new_password: '' });
  const [savingPw, setSavingPw] = useState<boolean>(false);

  // New Doctor registration (Administrator only)
  const [showNewUser, setShowNewUser] = useState<boolean>(false);
  const [newUserForm, setNewUserForm] = useState({
    username: '',
    password: '',
    full_name: '',
    credentials: 'MD',
    designation: 'Consultant Radiologist',
    role: 'Radiologist' as DoctorRole,
    department: 'Department of Radiology & Sonography',
    email: '',
  });
  const [creatingUser, setCreatingUser] = useState<boolean>(false);

  useEffect(() => {
    if (user) {
      setProfileForm({
        full_name: user.full_name || '',
        credentials: user.credentials || '',
        designation: user.designation || '',
        department: user.department || '',
        email: user.email || '',
      });
    }
  }, [user]);

  const loadSettingsData = async () => {
    try {
      const promises: Promise<any>[] = [
        api.getEngineStatus(),
        api.getExportsStatus(),
      ];
      if (isAdmin) {
        promises.push(api.getBackups(), api.listUsers());
      }
      const results = await Promise.all(promises);
      setEngineStatus(results[0]);
      setExportStatus(results[1]);
      if (isAdmin) {
        setBackups(results[2]?.backups || []);
        if (results[3]) setTeamUsers(results[3]);
      } else {
        setBackups([]);
      }
    } catch (err) {
      console.error('Failed to load settings', err);
    }
  };

  useEffect(() => {
    loadSettingsData();
  }, [isAdmin]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSavingProfile(true);
      setMessage(null);
      await api.updateProfile(profileForm);
      await refreshUser();
      setMessage({ text: 'Doctor profile updated successfully.', type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to update profile.', type: 'error' });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSavingPw(true);
      setMessage(null);
      await api.changePassword(pwForm.current_password, pwForm.new_password);
      setPwForm({ current_password: '', new_password: '' });
      setMessage({ text: 'Password updated successfully.', type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Password change failed.', type: 'error' });
    } finally {
      setSavingPw(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreatingUser(true);
      setMessage(null);
      await api.createUser(newUserForm);
      setShowNewUser(false);
      setNewUserForm({
        username: '',
        password: '',
        full_name: '',
        credentials: 'MD',
        designation: 'Consultant Radiologist',
        role: 'Radiologist',
        department: 'Department of Radiology & Sonography',
        email: '',
      });
      await loadSettingsData();
      setMessage({ text: 'Doctor account created successfully.', type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to create doctor account.', type: 'error' });
    } finally {
      setCreatingUser(false);
    }
  };

  const handleToggleUserRole = async (target: DoctorUser) => {
    const nextRole: DoctorRole = target.role === 'Administrator' ? 'Radiologist' : 'Administrator';
    try {
      await api.updateUser(target.id, { role: nextRole });
      await loadSettingsData();
      setMessage({ text: `Updated ${target.full_name} role to ${nextRole}.`, type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to update role.', type: 'error' });
    }
  };

  const handleToggleUserActive = async (target: DoctorUser) => {
    try {
      await api.updateUser(target.id, { is_active: !target.is_active });
      await loadSettingsData();
      setMessage({
        text: `${target.full_name} account ${target.is_active ? 'deactivated' : 'activated'}.`,
        type: 'success',
      });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to update status.', type: 'error' });
    }
  };

  const handleCreateBackup = async () => {
    try {
      setBackupLoading(true);
      setMessage(null);
      const res = await api.createBackup();
      setMessage({ text: `Database backup created: ${res.filename}`, type: 'success' });
      await loadSettingsData();
    } catch (err: any) {
      setMessage({ text: `Backup failed: ${err.message}`, type: 'error' });
    } finally {
      setBackupLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Doctor Profile &amp; System Administration</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Manage your clinical sign-off profile, account security, team roles, and local diagnostic services
        </p>
      </div>

      {message && (
        <div
          className={`p-3.5 rounded-xl text-xs flex items-center gap-2 ${
            message.type === 'success'
              ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
              : 'bg-red-50 border border-red-200 text-red-800'
          }`}
        >
          {message.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-600" />
          ) : (
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Authenticated Doctor Profile & Password */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <form
          onSubmit={handleSaveProfile}
          className="lg:col-span-2 bg-white border border-slate-200 rounded-xl shadow-xs p-5 space-y-4"
        >
          <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
            <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
              <UserCheck className="w-4 h-4 text-teal-600" />
              <span>Authenticated Doctor Profile</span>
            </div>
            {user && (
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider border ${
                  isAdmin
                    ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                    : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                }`}
              >
                {user.role}
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase text-slate-500">Full Name</label>
              <input
                type="text"
                required
                value={profileForm.full_name}
                onChange={e => setProfileForm({ ...profileForm, full_name: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-teal-500"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase text-slate-500">Credentials</label>
              <input
                type="text"
                value={profileForm.credentials}
                onChange={e => setProfileForm({ ...profileForm, credentials: e.target.value })}
                placeholder="e.g. MD, DNB"
                className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-teal-500"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase text-slate-500">Designation</label>
              <input
                type="text"
                value={profileForm.designation}
                onChange={e => setProfileForm({ ...profileForm, designation: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-teal-500"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase text-slate-500">Department</label>
              <input
                type="text"
                value={profileForm.department}
                onChange={e => setProfileForm({ ...profileForm, department: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-teal-500"
              />
            </div>
            <div className="sm:col-span-2 space-y-1">
              <label className="text-[10px] font-bold uppercase text-slate-500">Institutional Email</label>
              <input
                type="email"
                value={profileForm.email}
                onChange={e => setProfileForm({ ...profileForm, email: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-teal-500"
              />
            </div>
          </div>

          <div className="pt-2 flex justify-between items-center text-[11px] text-slate-500">
            <span>
              Username: <strong className="font-mono text-slate-800">{user?.username}</strong>
            </span>
            <button
              type="submit"
              disabled={savingProfile}
              className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white font-bold text-xs rounded-lg transition cursor-pointer"
            >
              {savingProfile ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        </form>

        <form
          onSubmit={handleChangePassword}
          className="bg-white border border-slate-200 rounded-xl shadow-xs p-5 space-y-4 flex flex-col justify-between"
        >
          <div className="space-y-3">
            <div className="flex items-center gap-2 pb-2.5 border-b border-slate-100 font-bold text-slate-900 text-sm">
              <KeyRound className="w-4 h-4 text-teal-600" />
              <span>Account Security</span>
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase text-slate-500">Current Password</label>
              <input
                type="password"
                required
                value={pwForm.current_password}
                onChange={e => setPwForm({ ...pwForm, current_password: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-teal-500"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase text-slate-500">New Password (min 6 chars)</label>
              <input
                type="password"
                required
                minLength={6}
                value={pwForm.new_password}
                onChange={e => setPwForm({ ...pwForm, new_password: e.target.value })}
                className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-teal-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={savingPw}
            className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-lg transition cursor-pointer"
          >
            {savingPw ? 'Updating...' : 'Update Password'}
          </button>
        </form>
      </div>

      {/* Role-Gated Doctor Accounts Management */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs p-5 space-y-4">
        <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
          <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
            <Users className="w-4 h-4 text-teal-600" />
            <span>Clinician &amp; Administrator Access</span>
          </div>
          {isAdmin && (
            <button
              type="button"
              onClick={() => setShowNewUser(prev => !prev)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg transition cursor-pointer"
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>{showNewUser ? 'Close Form' : 'Add Doctor Account'}</span>
            </button>
          )}
        </div>

        {!isAdmin ? (
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 flex items-center gap-2">
            <Shield className="w-4 h-4 text-slate-500 shrink-0" />
            <span>
              Signed in with <strong>Radiologist</strong> permissions. Adding doctor accounts or managing roles requires{' '}
              <strong>Administrator</strong> privileges.
            </span>
          </div>
        ) : (
          <>
            {showNewUser && (
              <form
                onSubmit={handleCreateUser}
                className="p-4 bg-slate-50 border border-slate-200 rounded-xl grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs"
              >
                <input
                  type="text"
                  required
                  placeholder="Username (e.g. cpan)"
                  value={newUserForm.username}
                  onChange={e => setNewUserForm({ ...newUserForm, username: e.target.value })}
                  className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg"
                />
                <input
                  type="password"
                  required
                  minLength={6}
                  placeholder="Password (min 6 chars)"
                  value={newUserForm.password}
                  onChange={e => setNewUserForm({ ...newUserForm, password: e.target.value })}
                  className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg"
                />
                <input
                  type="text"
                  required
                  placeholder="Full Name (e.g. Dr. Aarav Sharma)"
                  value={newUserForm.full_name}
                  onChange={e => setNewUserForm({ ...newUserForm, full_name: e.target.value })}
                  className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg"
                />
                <input
                  type="text"
                  placeholder="Credentials (e.g. MD)"
                  value={newUserForm.credentials}
                  onChange={e => setNewUserForm({ ...newUserForm, credentials: e.target.value })}
                  className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg"
                />
                <select
                  value={newUserForm.role}
                  onChange={e => setNewUserForm({ ...newUserForm, role: e.target.value as DoctorRole })}
                  className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg"
                >
                  <option value="Radiologist">Radiologist</option>
                  <option value="Administrator">Administrator</option>
                </select>
                <button
                  type="submit"
                  disabled={creatingUser}
                  className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-lg cursor-pointer"
                >
                  {creatingUser ? 'Registering...' : 'Create Account'}
                </button>
              </form>
            )}

            <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden text-xs">
              {teamUsers.map(u => (
                <div key={u.id} className="py-2.5 px-3.5 flex flex-wrap items-center justify-between gap-3 bg-white">
                  <div>
                    <div className="font-bold text-slate-900">
                      {u.display_name}{' '}
                      <span className="font-mono text-[11px] font-normal text-slate-500">(@{u.username})</span>
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {u.designation || u.role} · {u.email || u.department}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                        u.role === 'Administrator'
                          ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      {u.role}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleToggleUserRole(u)}
                      className="px-2.5 py-1 text-[11px] font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded cursor-pointer"
                    >
                      Switch Role
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleUserActive(u)}
                      className={`px-2.5 py-1 text-[11px] font-semibold rounded border cursor-pointer ${
                        u.is_active
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-rose-50 hover:text-rose-700'
                          : 'bg-rose-50 border-rose-200 text-rose-700 hover:bg-emerald-50 hover:text-emerald-700'
                      }`}
                    >
                      {u.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Speech Recognition & Export Engines */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-white border border-slate-200 rounded-xl shadow-xs p-4 space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 font-bold text-slate-900 text-sm">
            <Cpu className="w-4 h-4 text-teal-600" />
            <span>Local Speech Engine</span>
          </div>
          <div className="grid grid-cols-2 gap-2.5 text-xs">
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Engine</div>
              <div className="font-bold text-slate-800 mt-0.5">{engineStatus?.engine || 'Faster-Whisper'}</div>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Active Model</div>
              <div className="font-bold text-teal-700 mt-0.5">{engineStatus?.active_model || 'small.en'}</div>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Device</div>
              <div className="font-bold text-slate-800 mt-0.5">{engineStatus?.device.toUpperCase() || 'CPU'}</div>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Precision</div>
              <div className="font-bold text-slate-800 mt-0.5">{engineStatus?.compute_type || 'int8'}</div>
            </div>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl shadow-xs p-4 space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 font-bold text-slate-900 text-sm">
            <FileCheck className="w-4 h-4 text-teal-600" />
            <span>Document Export Services</span>
          </div>
          <div className="space-y-2.5 text-xs">
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100 flex items-center justify-between">
              <span className="font-semibold text-slate-700">Word (.docx) Template Engine</span>
              <span className="text-emerald-700 font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Ready
              </span>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100 flex items-center justify-between">
              <span className="font-semibold text-slate-700">
                PDF Export ({exportStatus?.pdf_engine || 'Headless Edge'})
              </span>
              <span className="text-emerald-700 font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Ready
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Database & Backups */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs p-4 space-y-3.5">
        <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
          <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
            <Database className="w-4 h-4 text-teal-600" />
            <span>Database Persistence &amp; Backups</span>
          </div>
          {isAdmin && (
            <button
              onClick={handleCreateBackup}
              disabled={backupLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition cursor-pointer shadow-xs"
            >
              <HardDrive className="w-3.5 h-3.5" />
              {backupLoading ? 'Creating Backup...' : 'Create Backup Now'}
            </button>
          )}
        </div>

        <div className="space-y-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
            Verified Snapshots ({backups.length})
          </span>
          {!backups.length ? (
            <div className="py-6 text-center text-xs text-slate-400">No backup snapshots recorded yet.</div>
          ) : (
            <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden text-xs">
              {backups.slice(0, 6).map(b => (
                <div key={b.filename} className="py-2 px-3 flex items-center justify-between bg-white">
                  <span className="font-mono text-slate-800">{b.filename}</span>
                  <span className="text-slate-500">{(b.size_bytes / 1024).toFixed(1)} KB</span>
                  <span className="text-slate-500">{b.created_at?.slice(0, 19).replace('T', ' ')}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
