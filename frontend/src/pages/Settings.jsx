import { useState, useEffect } from 'react';
import { settingsAPI } from '../services/api';

export default function Settings() {
  const [autoInvite, setAutoInvite] = useState(false);
  const [threshold, setThreshold] = useState(75);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    settingsAPI.get().then((res) => {
      setAutoInvite(res.data.auto_invite_screening);
      setThreshold(res.data.auto_invite_threshold);
    }).catch((err) => {
      console.error('Failed to load settings', err);
    }).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const res = await settingsAPI.update({
        auto_invite_screening: autoInvite,
        auto_invite_threshold: threshold,
      });
      setAutoInvite(res.data.auto_invite_screening);
      setThreshold(res.data.auto_invite_threshold);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to save settings', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        Loading...
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-3xl font-bold text-slate-900">Settings</h1>

      <div className="card p-6 max-w-xl space-y-5">
        <h2 className="text-lg font-semibold text-slate-800">Screening Automation</h2>
        <p className="text-sm text-slate-500">
          Automatically invite candidates to a screening interview when their resume match score meets the threshold.
        </p>

        {/* Toggle */}
        <label className="flex items-center gap-3 cursor-pointer">
          <button
            type="button"
            role="switch"
            aria-checked={autoInvite}
            onClick={() => setAutoInvite((v) => !v)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              autoInvite ? 'bg-blue-600' : 'bg-slate-300'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                autoInvite ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
          <span className="text-sm font-medium text-slate-700">
            Auto-invite to screening
          </span>
        </label>

        {/* Threshold (visible when toggle is on) */}
        {autoInvite && (
          <div className="space-y-1">
            <label className="block text-sm font-medium text-slate-700">
              Minimum resume match score (%)
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={threshold}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (!isNaN(v)) setThreshold(Math.max(1, Math.min(100, v)));
              }}
              className="w-28 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-slate-400">
              Candidates scoring at or above this threshold will be auto-invited.
            </p>
          </div>
        )}

        {/* Save */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
          {saved && (
            <span className="text-sm text-emerald-600 font-medium">Settings saved</span>
          )}
        </div>
      </div>
    </div>
  );
}
