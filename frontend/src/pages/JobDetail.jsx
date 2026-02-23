import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  MapPin,
  Building2,
  Briefcase,
  DollarSign,
  Users,
  Star,
  X,
  Mail,
  CheckCircle,
  MessageSquare,
  CheckSquare,
  Square,
  ChevronRight,
  ChevronDown,
  Zap,
} from 'lucide-react';
import { jobsAPI, applicationsAPI, screeningsAPI } from '../services/api';

// ─── helpers ────────────────────────────────────────────────────────────────

const JOB_STATUS_BADGE = {
  draft:   'bg-slate-100 text-slate-600',
  active:  'bg-emerald-100 text-emerald-700',
  paused:  'bg-amber-100 text-amber-700',
  closed:  'bg-red-100 text-red-700',
};

const APP_STATUS_BADGE = {
  pending:     'bg-slate-100 text-slate-600',
  screening:   'bg-blue-100 text-blue-700',
  shortlisted: 'bg-indigo-100 text-indigo-700',
  interview:   'bg-purple-100 text-purple-700',
  offered:     'bg-teal-100 text-teal-700',
  hired:       'bg-emerald-100 text-emerald-700',
  rejected:    'bg-red-100 text-red-600',
};

const SCORE_BADGE = (score) => {
  if (score == null) return 'bg-slate-100 text-slate-500';
  if (score >= 75) return 'bg-emerald-100 text-emerald-700';
  if (score >= 55) return 'bg-amber-100 text-amber-700';
  return 'bg-red-100 text-red-600';
};


const formatSalary = (min, max) => {
  if (!min && !max) return null;
  const fmt = (n) => `$${(n / 1000).toFixed(0)}k`;
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (min) return `From ${fmt(min)}`;
  return `Up to ${fmt(max)}`;
};

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

// ─── Pipeline Funnel ─────────────────────────────────────────────────────────

const FUNNEL_LABELS = {
  applied:     'Applied',
  screening:   'Screening Invited',
  shortlisted: 'Screening Passed',
  rejected:    'Rejected',
};

function PipelineFunnel({ pipeline, activeStage, onStageClick }) {
  const total = pipeline?.total || 0;

  return (
    <div className="card p-6">
      <div className="flex items-start gap-6">
        {/* Funnel bars */}
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">
            Hiring Funnel
          </h2>
          <div className="flex gap-1 items-end h-20">
            {(pipeline?.funnel || []).map((item) => {
              const pct = total > 0 ? Math.max((item.count / total) * 100, 4) : 4;
              const isActive = activeStage === item.stage;
              const colours = {
                applied:     'bg-blue-500 hover:bg-blue-600',
                screening:   'bg-indigo-500 hover:bg-indigo-600',
                shortlisted: 'bg-emerald-500 hover:bg-emerald-600',
                rejected:    'bg-red-400 hover:bg-red-500',
              };
              return (
                <button
                  key={item.stage}
                  onClick={() => onStageClick(item.stage === activeStage ? null : item.stage)}
                  className={`flex-1 rounded-t-md transition-all duration-200 relative group cursor-pointer
                    ${colours[item.stage]}
                    ${isActive ? 'ring-2 ring-offset-1 ring-slate-700' : ''}`}
                  style={{ height: `${pct}%` }}
                  title={`${FUNNEL_LABELS[item.stage]}: ${item.count}`}
                >
                  <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-xs font-semibold text-slate-700 whitespace-nowrap">
                    {item.count}
                  </span>
                </button>
              );
            })}
          </div>
          {/* Labels below bars */}
          <div className="flex gap-1 mt-1">
            {(pipeline?.funnel || []).map((item) => (
              <div key={item.stage} className="flex-1 text-center text-xs text-slate-500 leading-tight px-1">
                {FUNNEL_LABELS[item.stage]}
              </div>
            ))}
          </div>
        </div>

        {/* Avg score card */}
        <div className="flex flex-col items-center justify-center bg-slate-50 rounded-xl px-6 py-4 min-w-[110px]">
          <Star className="w-5 h-5 text-amber-400 mb-1" />
          <span className="text-2xl font-bold text-slate-800">
            {pipeline?.avg_match_score ?? '–'}
          </span>
          <span className="text-xs text-slate-500 text-center mt-0.5">Avg Resume Match</span>
        </div>
      </div>
    </div>
  );
}

// ─── Stage Filter Strip ──────────────────────────────────────────────────────

const FILTER_PILLS = [
  { label: 'All',         value: null },
  { label: 'Applied',     value: 'pending' },
  { label: 'Screening',   value: 'screening' },
  { label: 'Shortlisted', value: 'shortlisted' },
  { label: 'Interview',   value: 'interview' },
  { label: 'Offered',     value: 'offered' },
  { label: 'Hired',       value: 'hired' },
  { label: 'Rejected',    value: 'rejected' },
];

// Map funnel stages → pill values
const FUNNEL_TO_PILL = {
  applied:     null,
  screening:   'screening',
  shortlisted: 'shortlisted',
  rejected:    'rejected',
};

function StageFilterStrip({ active, onSelect }) {
  return (
    <div className="flex flex-wrap gap-2">
      {FILTER_PILLS.map((pill) => {
        const isActive = active === pill.value;
        return (
          <button
            key={pill.label}
            onClick={() => onSelect(pill.value)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors
              ${isActive
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
          >
            {pill.label}
          </button>
        );
      })}
    </div>
  );
}

// ─── Note Modal ──────────────────────────────────────────────────────────────

function NoteModal({ application, onClose, onSave }) {
  const [notes, setNotes] = useState(application?.notes || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(application.id, notes);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-800">
            Note — {application?.candidate?.full_name}
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        </div>
        <textarea
          className="w-full border border-slate-200 rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={5}
          placeholder="Add a note about this candidate…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save note'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Screening result helpers ─────────────────────────────────────────────────

function screeningResult(s) {
  if (s.status === 'cancelled')   return { label: 'Cancelled', cls: 'bg-slate-100 text-slate-500' };
  if (s.status === 'scheduled')   return { label: 'Pending',   cls: 'bg-slate-100 text-slate-500' };
  if (s.status === 'in_progress') return { label: 'In Progress', cls: 'bg-blue-100 text-blue-700' };
  // completed — use recommendation
  if (['strong_pass', 'pass'].includes(s.recommendation)) return { label: 'Pass', cls: 'bg-emerald-100 text-emerald-700' };
  if (s.recommendation === 'borderline') return { label: 'Borderline', cls: 'bg-amber-100 text-amber-700' };
  return { label: 'Fail', cls: 'bg-red-100 text-red-600' };
}

function SourceBadge({ source }) {
  if (source === 'auto') return <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-700">Auto</span>;
  if (source === 'bulk') return <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-700">Bulk</span>;
  return null;
}

// ─── Candidate Row ────────────────────────────────────────────────────────────

function CandidateRow({ app, selected, onToggle, onAction, onOpenNote }) {
  const [showHistory, setShowHistory] = useState(false);

  const screenings = (app.screenings || [])
    .slice()
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

  const latestScreening = screenings.length > 0 ? screenings[screenings.length - 1] : null;
  const isAutoInvited = latestScreening?.source === 'auto';

  // Only block invite if a screening is currently active (scheduled or in_progress).
  // Completed, cancelled, or no prior screenings → recruiter can always send a new invite.
  const hasActiveScreening = screenings.some(s => ['scheduled', 'in_progress'].includes(s.status));
  const disableApprove = ['shortlisted', 'interview', 'offered', 'hired'].includes(app.status);
  const disableReject  = app.status === 'rejected';

  const colSpan = 6;

  return (
    <>
      <tr className="hover:bg-slate-50 transition-colors">
        {/* Checkbox */}
        <td className="px-4 py-3 w-8">
          <button onClick={() => onToggle(app.id)} className="text-slate-400 hover:text-blue-600">
            {selected ? (
              <CheckSquare className="w-4 h-4 text-blue-600" />
            ) : (
              <Square className="w-4 h-4" />
            )}
          </button>
        </td>

        {/* Candidate */}
        <td className="px-4 py-3">
          <div className="font-medium text-slate-800 text-sm flex items-center gap-1.5">
            {app.candidate?.full_name}
            {isAutoInvited && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 text-[10px] font-semibold" title="Auto-invited to screening">
                <Zap className="w-2.5 h-2.5" /> Auto-invited
              </span>
            )}
          </div>
          <div className="text-xs text-slate-500">{app.candidate?.email}</div>
          {screenings.length > 0 && (
            <button
              onClick={() => setShowHistory(h => !h)}
              className="mt-1 inline-flex items-center gap-0.5 text-xs text-blue-600 hover:underline"
            >
              {showHistory ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {screenings.length} screening round{screenings.length > 1 ? 's' : ''}
            </button>
          )}
        </td>

        {/* Resume Match */}
        <td className="px-4 py-3 text-center">
          {app.match_score != null
            ? <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${SCORE_BADGE(app.match_score)}`}>{app.match_score}%</span>
            : <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-400">No resume</span>
          }
        </td>

        {/* Applied date */}
        <td className="px-4 py-3 text-sm text-slate-500 whitespace-nowrap">
          {formatDate(app.applied_at)}
        </td>

        {/* Status badge */}
        <td className="px-4 py-3">
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${APP_STATUS_BADGE[app.status] || 'bg-slate-100 text-slate-600'}`}>
            {app.status}
          </span>
        </td>

        {/* Actions */}
        <td className="px-4 py-3">
          <div className="flex items-center gap-1">
            <button
              disabled={hasActiveScreening}
              onClick={() => onAction('invite', app.id)}
              title={hasActiveScreening ? 'Screening already in progress' : 'Send screening invite'}
              className="p-1.5 rounded hover:bg-blue-50 text-blue-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <Mail className="w-3.5 h-3.5" />
            </button>
            <button
              disabled={disableApprove}
              onClick={() => onAction('approve', app.id)}
              title="Approve candidate"
              className="p-1.5 rounded hover:bg-emerald-50 text-emerald-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <CheckCircle className="w-3.5 h-3.5" />
            </button>
            <button
              disabled={disableReject}
              onClick={() => onAction('reject', app.id)}
              title="Reject"
              className="p-1.5 rounded hover:bg-red-50 text-red-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onOpenNote(app)}
              title="Add / edit note"
              className="p-1.5 rounded hover:bg-slate-100 text-slate-500 transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5" />
            </button>
          </div>
        </td>
      </tr>

      {/* Screening history sub-row */}
      {showHistory && screenings.length > 0 && (
        <tr className="bg-slate-50">
          <td colSpan={colSpan} className="px-4 pb-3 pt-0">
            <div className="ml-8 border border-slate-200 rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-100 text-slate-500">
                    <th className="px-3 py-2 text-left font-medium">Round</th>
                    <th className="px-3 py-2 text-left font-medium">Date</th>
                    <th className="px-3 py-2 text-left font-medium">Result</th>
                    <th className="px-3 py-2 text-left font-medium">Score</th>
                    <th className="px-3 py-2 text-left font-medium">Technical</th>
                    <th className="px-3 py-2 text-left font-medium">Communication</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {screenings.map((s, i) => {
                    const result = screeningResult(s);
                    return (
                      <tr key={s.id}>
                        <td className="px-3 py-2 font-medium text-slate-700 whitespace-nowrap">#{i + 1}<SourceBadge source={s.source} /></td>
                        <td className="px-3 py-2 text-slate-500 whitespace-nowrap">
                          {formatDate(s.scheduled_at || s.created_at)}
                        </td>
                        <td className="px-3 py-2">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${result.cls}`}>
                            {result.label}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {s.overall_score != null ? `${s.overall_score}%` : '–'}
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {s.technical_score != null ? `${s.technical_score}%` : '–'}
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {s.communication_score != null ? `${s.communication_score}%` : '–'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function JobDetail() {
  const { id } = useParams();

  const [job, setJob]               = useState(null);
  const [pipeline, setPipeline]     = useState(null);
  const [applications, setApplications] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [funnelStage, setFunnelStage]   = useState(null);

  // Bulk select
  const [selected, setSelected]     = useState(new Set());

  // Note modal
  const [noteApp, setNoteApp]       = useState(null);

  // ── data loading ──────────────────────────────────────────────────────────

  const loadPipeline = useCallback(async () => {
    try {
      const res = await jobsAPI.getPipeline(id);
      setPipeline(res.data);
    } catch (err) {
      console.error('Failed to load pipeline', err);
    }
  }, [id]);

  const loadApplications = useCallback(async (filter) => {
    try {
      const params = { job_id: id };
      if (filter) params.status = filter;
      const res = await applicationsAPI.getAll(params);
      setApplications(res.data);
    } catch (err) {
      console.error('Failed to load applications', err);
    }
  }, [id]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const [jobRes] = await Promise.all([
          jobsAPI.getById(id),
          loadPipeline(),
          loadApplications(null),
        ]);
        setJob(jobRes.data);
      } catch (err) {
        console.error('Failed to load job', err);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [id, loadPipeline, loadApplications]);

  // Sync filter when funnel stage clicked
  const handleFunnelStageClick = (stage) => {
    setFunnelStage(stage);
    const pill = stage ? FUNNEL_TO_PILL[stage] : null;
    setStatusFilter(pill !== undefined ? pill : null);
    loadApplications(pill !== undefined ? pill : null);
    setSelected(new Set());
  };

  const handlePillSelect = (value) => {
    setStatusFilter(value);
    setFunnelStage(null);
    loadApplications(value);
    setSelected(new Set());
  };

  // ── inline actions ────────────────────────────────────────────────────────

  const refreshAll = async () => {
    await Promise.all([loadPipeline(), loadApplications(statusFilter)]);
  };

  const updateRow = (updated) => {
    setApplications((prev) => prev.map((a) => (a.id === updated.id ? { ...a, ...updated } : a)));
  };

  const handleAction = async (type, appId) => {
    try {
      let res;
      if (type === 'invite') {
        res = await screeningsAPI.create({ application_id: appId });
        updateRow({ id: appId, status: 'screening' });
      } else if (type === 'approve') {
        res = await applicationsAPI.shortlist(appId);
        updateRow(res.data);
      } else if (type === 'reject') {
        res = await applicationsAPI.reject(appId);
        updateRow(res.data);
      }
      await loadPipeline();
    } catch (err) {
      console.error(`Action ${type} failed`, err);
    }
  };

  const handleSaveNote = async (appId, notes) => {
    const res = await applicationsAPI.update(appId, { notes });
    updateRow(res.data);
  };

  // ── bulk select ───────────────────────────────────────────────────────────

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === applications.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(applications.map((a) => a.id)));
    }
  };

  // ── bulk invite ───────────────────────────────────────────────────────────

  const [bulkLoading, setBulkLoading] = useState(false);

  const handleBulkInvite = async () => {
    setBulkLoading(true);
    try {
      await applicationsAPI.bulkInviteScreening([...selected]);
      setSelected(new Set());
      await refreshAll();
    } catch (err) {
      console.error('Bulk invite failed', err);
    } finally {
      setBulkLoading(false);
    }
  };

  // ── job header actions ────────────────────────────────────────────────────

  const handleJobAction = async (action) => {
    try {
      let res;
      if (action === 'publish') res = await jobsAPI.publish(id);
      else if (action === 'close')   res = await jobsAPI.close(id);
      else if (action === 'pause')   res = await jobsAPI.update(id, { status: 'paused' });
      else if (action === 'reopen')  res = await jobsAPI.update(id, { status: 'active' });
      if (res) setJob(res.data);
    } catch (err) {
      console.error('Job action failed', err);
    }
  };

  // ── render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        Loading…
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <p className="text-slate-500">Job not found.</p>
        <Link to="/jobs" className="text-blue-600 hover:underline text-sm">← Back to Jobs</Link>
      </div>
    );
  }

  const salary = formatSalary(job.salary_min, job.salary_max);
  const allSelected = applications.length > 0 && selected.size === applications.length;

  return (
    <div className="space-y-6 pb-24 animate-fade-in">

      {/* Back link */}
      <Link to="/jobs" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-blue-600 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to Jobs
      </Link>

      {/* ── Job Header ── */}
      <div className="card p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">{job.title}</h1>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${JOB_STATUS_BADGE[job.status] || 'bg-slate-100 text-slate-600'}`}>
                {job.status}
              </span>
            </div>

            <div className="flex flex-wrap gap-4 text-sm text-slate-500">
              {job.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" /> {job.location}
                </span>
              )}
              {job.department && (
                <span className="flex items-center gap-1">
                  <Building2 className="w-3.5 h-3.5" /> {job.department}
                </span>
              )}
              {job.job_type && (
                <span className="flex items-center gap-1">
                  <Briefcase className="w-3.5 h-3.5" /> {job.job_type.replace('_', ' ')}
                </span>
              )}
              {salary && (
                <span className="flex items-center gap-1">
                  <DollarSign className="w-3.5 h-3.5" /> {salary}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Users className="w-3.5 h-3.5" /> {job.applications_count ?? 0} applicants
              </span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap">
            {job.status === 'draft'  && (
              <button onClick={() => handleJobAction('publish')} className="px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors">
                Publish
              </button>
            )}
            {job.status === 'active' && (
              <>
                <button onClick={() => handleJobAction('pause')} className="px-4 py-2 text-sm bg-amber-500 text-white rounded-lg hover:bg-amber-600 transition-colors">
                  Pause
                </button>
                <button onClick={() => handleJobAction('close')} className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors">
                  Close
                </button>
              </>
            )}
            {job.status === 'paused' && (
              <>
                <button onClick={() => handleJobAction('reopen')} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                  Reopen
                </button>
                <button onClick={() => handleJobAction('close')} className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors">
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Pipeline Funnel ── */}
      <PipelineFunnel
        pipeline={pipeline}
        activeStage={funnelStage}
        onStageClick={handleFunnelStageClick}
      />

      {/* ── Stage Filter Strip ── */}
      <StageFilterStrip active={statusFilter} onSelect={handlePillSelect} />

      {/* ── Candidate Table ── */}
      <div className="card overflow-hidden">
        {applications.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm">
            No candidates match this filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="px-4 py-3 text-left w-8">
                    <button onClick={toggleAll} className="text-slate-400 hover:text-blue-600">
                      {allSelected ? (
                        <CheckSquare className="w-4 h-4 text-blue-600" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Candidate</th>
                  <th className="px-4 py-3 text-center font-semibold text-slate-600">Resume Match</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Applied</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Status</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {applications.map((app) => (
                  <CandidateRow
                    key={app.id}
                    app={app}
                    selected={selected.has(app.id)}
                    onToggle={toggleSelect}
                    onAction={handleAction}
                    onOpenNote={setNoteApp}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Sticky Bulk Action Bar ── */}
      {selected.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 z-40 flex items-center justify-center pb-4 pointer-events-none">
          <div className="pointer-events-auto flex items-center gap-4 bg-slate-900 text-white px-6 py-3 rounded-xl shadow-2xl">
            <span className="text-sm font-medium">
              {selected.size} selected
            </span>
            <button
              onClick={handleBulkInvite}
              disabled={bulkLoading}
              className="px-4 py-1.5 text-sm bg-blue-500 hover:bg-blue-600 rounded-lg font-medium disabled:opacity-50 transition-colors"
            >
              {bulkLoading ? 'Inviting…' : 'Invite to Screening'}
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className="text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── Note Modal ── */}
      {noteApp && (
        <NoteModal
          application={noteApp}
          onClose={() => setNoteApp(null)}
          onSave={handleSaveNote}
        />
      )}
    </div>
  );
}
