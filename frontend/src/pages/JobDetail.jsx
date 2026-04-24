import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
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
  Settings,
  Clock,
  HelpCircle,
  ChevronUp,
  Save,
  PlayCircle,
  Loader2,
  BarChart3,
} from 'lucide-react';
import { jobsAPI, applicationsAPI, screeningsAPI } from '../services/api';
import axios from 'axios';

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

function CandidateRow({ app, selected, onToggle, onAction, onOpenNote, onViewReport }) {
  const [inviting, setInviting] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const screenings = (app.screenings || [])
    .slice()
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

  const latestScreening = screenings.length > 0 ? screenings[screenings.length - 1] : null;
  const isAutoInvited = latestScreening?.source === 'auto';

  // Only block invite if a screening is currently active (scheduled or in_progress).
  // Completed, cancelled, or no prior screenings → recruiter can always send a new invite.
  const hasActiveScreening = screenings.some(s => s.status === 'in_progress');
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
              disabled={hasActiveScreening || inviting}
              onClick={async () => { setInviting(true); await onAction('invite', app.id); setInviting(false); }}
              title={hasActiveScreening ? 'Screening already in progress' : 'Send screening invite'}
              className="p-1.5 rounded hover:bg-blue-50 text-blue-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              {inviting
                ? <div className="w-3.5 h-3.5 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin" />
                : <Mail className="w-3.5 h-3.5" />}
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
                    <th className="px-3 py-2 text-left font-medium">Report</th>
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
                        <td className="px-3 py-2">
                          {s.ai_evaluation && (
                            <button
                              onClick={() => onViewReport && onViewReport(s)}
                              className="text-xs text-primary-600 hover:underline font-medium"
                            >
                              View Report
                            </button>
                          )}
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


// ─── Report Modal ─────────────────────────────────────────────────────────────

function ReportModal({ screening, onClose }) {
  if (!screening) return null
  let ev = {}
  try { ev = JSON.parse(screening.ai_evaluation || '{}') } catch (_) {}
  const perQ = ev.per_question || []
  const pass = screening.recommendation === 'pass' || screening.recommendation === 'strong_pass'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h3 className="text-base font-semibold text-slate-800">Screening Report</h3>
            <p className="text-xs text-slate-500 mt-0.5">Round result: <span className={pass ? 'text-emerald-600 font-medium' : 'text-red-600 font-medium'}>{pass ? 'Pass' : 'Did not pass'}</span></p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-5">
          {/* Score */}
          <div className="flex items-center gap-4">
            <div className={`w-16 h-16 rounded-full border-4 flex items-center justify-center font-bold text-lg
              ${screening.overall_score >= 70 ? 'border-emerald-400 text-emerald-600' : screening.overall_score >= 50 ? 'border-amber-400 text-amber-600' : 'border-red-400 text-red-600'}`}>
              {screening.overall_score ?? '–'}
            </div>
            <p className="text-slate-600 text-sm flex-1">{ev.summary}</p>
          </div>

          {/* Strengths / Weaknesses */}
          {(ev.strengths?.length > 0 || ev.weaknesses?.length > 0) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold text-emerald-700 mb-2">Strengths</p>
                <ul className="space-y-1">{(ev.strengths || []).map((s,i) => <li key={i} className="text-slate-600 text-xs">• {s}</li>)}</ul>
              </div>
              <div>
                <p className="text-xs font-semibold text-red-600 mb-2">Areas to Improve</p>
                <ul className="space-y-1">{(ev.weaknesses || []).map((w,i) => <li key={i} className="text-slate-600 text-xs">• {w}</li>)}</ul>
              </div>
            </div>
          )}

          {/* Recommendation */}
          {ev.hiring_recommendation && (
            <div className="bg-slate-50 rounded-xl p-4">
              <p className="text-xs font-semibold text-slate-700 mb-1">Hiring Recommendation</p>
              <p className="text-slate-600 text-sm">{ev.hiring_recommendation}</p>
            </div>
          )}

          {/* Per question */}
          {perQ.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-700 mb-3">Per-Question Breakdown</p>
              <div className="space-y-2">
                {perQ.map((pq, i) => (
                  <div key={i} className="border border-slate-100 rounded-xl p-3">
                    <div className="flex justify-between items-start gap-3 mb-1">
                      <p className="text-slate-700 text-xs font-medium flex-1">{pq.question}</p>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0
                        ${pq.score >= 70 ? 'bg-emerald-50 text-emerald-600' : pq.score >= 50 ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-600'}`}>
                        {pq.score}/100
                      </span>
                    </div>
                    <p className="text-slate-500 text-xs">{pq.feedback}</p>
                    {pq.what_was_good && <p className="text-emerald-600 text-xs mt-1">✓ {pq.what_was_good}</p>}
                    {pq.what_was_missing && <p className="text-red-500 text-xs mt-0.5">✗ {pq.what_was_missing}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function JobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

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

  // Report modal
  const [reportScreening, setReportScreening] = useState(null);

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

  // Poll setup status while generating
  const startSetupPolling = useCallback((jobId) => {
    clearInterval(setupPollRef.current);
    setupPollRef.current = setInterval(async () => {
      try {
        const res = await jobsAPI.getSetupStatus(jobId);
        const { setup_status, progress_current, progress_total } = res.data;
        setSetupStatus(setup_status);
        setSetupProgress({ current: progress_current || 0, total: progress_total || 0 });
        if (setup_status === 'ready' || setup_status === 'failed') {
          clearInterval(setupPollRef.current);
          // Refresh job data to get updated setup_status
          const jobRes = await jobsAPI.getById(jobId);
          setJob(jobRes.data);
        }
      } catch (_) {}
    }, 3000);
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const [jobRes] = await Promise.all([
          jobsAPI.getById(id),
          loadPipeline(),
          loadApplications(null),
        ]);
        const jobData = jobRes.data;
        setJob(jobData);
        // Treat null (never set up) the same as 'generating' — backend will auto-trigger setup
        const effectiveStatus = jobData.setup_status ?? 'generating';
        setSetupStatus(effectiveStatus);
        if (effectiveStatus === 'generating') {
          startSetupPolling(id);
        }
      } catch (err) {
        console.error('Failed to load job', err);
      } finally {
        setLoading(false);
      }
    };
    init();
    return () => clearInterval(setupPollRef.current);
  }, [id, loadPipeline, loadApplications, startSetupPolling]);

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
        await Promise.all([loadPipeline(), loadApplications(statusFilter)]);
      } else if (type === 'approve') {
        res = await applicationsAPI.shortlist(appId);
        updateRow(res.data);
        await loadPipeline();
      } else if (type === 'reject') {
        res = await applicationsAPI.reject(appId);
        updateRow(res.data);
        await loadPipeline();
      }
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
  const [showScreeningConfig, setShowScreeningConfig] = useState(false);
  const [screeningConfig, setScreeningConfig] = useState(null);
  const [savingConfig, setSavingConfig] = useState(false);
  const [configSaved, setConfigSaved] = useState(false);
  const [launchingMock, setLaunchingMock] = useState(false);

  // Setup status polling
  const [setupStatus, setSetupStatus] = useState(null); // null | 'generating' | 'ready' | 'failed'
  const [setupProgress, setSetupProgress] = useState({ current: 0, total: 0 });
  const setupPollRef = useRef(null);

  // Video interview mode
  const [videoModeEnabled, setVideoModeEnabled] = useState(false);
  const [jobQuestions, setJobQuestions] = useState([]);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState(null);
  const INTERVIEW_API = import.meta.env.VITE_INTERVIEW_API_URL || 'http://localhost:8001';

  // Fetch video mode + question list when setup is ready
  useEffect(() => {
    if (setupStatus !== 'ready' || !id) return;
    const load = async () => {
      try {
        const res = await axios.get(`${INTERVIEW_API}/api/interview/job/${id}/setup/status`);
        setVideoModeEnabled(!!res.data.video_interview_enabled);
        // Fetch only the questions belonging to this job using the job's domain
        const domain = res.data.domain || 'all';
        const qRes = await axios.get(`${INTERVIEW_API}/api/interview/question-bank`, {
          params: { domain, job_id: id, limit: 50 }
        });
        setJobQuestions(qRes.data.questions || []);
      } catch (err) {
        console.warn('[JobDetail] Failed to load question bank:', err?.message);
        // Retry once after 3s
        setTimeout(async () => {
          try {
            const res = await axios.get(`${INTERVIEW_API}/api/interview/job/${id}/setup/status`);
            const domain = res.data.domain || 'all';
            const qRes = await axios.get(`${INTERVIEW_API}/api/interview/question-bank`, {
              params: { domain, job_id: id, limit: 50 }
            });
            setJobQuestions(qRes.data.questions || []);
          } catch (_) {}
        }, 3000);
      }
    };
    load();
  }, [setupStatus, id, INTERVIEW_API]);

  // Toggle is local-only — persisted + video generation triggered on Save Config
  const toggleVideoMode = () => setVideoModeEnabled(v => !v);

  const toggleCoreCompetency = async (questionId, currentlyEnabled) => {
    const jd = [job?.description, job?.requirements, job?.responsibilities].filter(Boolean).join('\n\n') || job?.title || '';
    try {
      await axios.put(`${INTERVIEW_API}/api/interview/question/${questionId}/core-competency`, {
        enabled: !currentlyEnabled,
        job_description: jd,
      });
      // Refresh question list — scope to this job's domain
      const statusRes = await axios.get(`${INTERVIEW_API}/api/interview/job/${id}/setup/status`).catch(() => ({ data: {} }));
      const domain = statusRes.data.domain || 'all';
      const res = await axios.get(`${INTERVIEW_API}/api/interview/question-bank`, {
        params: { domain, job_id: id, limit: 50 }
      });
      setJobQuestions(res.data.questions || []);
    } catch (e) {
      console.error('Failed to toggle core competency', e);
    }
  };

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

  // Initialise screeningConfig from job on first render
  if (screeningConfig === null && job) {
    setScreeningConfig({
      time_limit: job.interview_time_limit ?? 45,
      num_questions: job.interview_num_questions ?? 8,
      difficulty: job.interview_difficulty ?? 3,
      seniority: job.interview_seniority ?? 'mid',
      behavioral_pct: job.interview_behavioral_pct ?? 20,
      verify_coding_ability: job.verify_coding_ability ?? false,
      auto_invite_screening: job.auto_invite_screening ?? false,
      auto_invite_threshold: job.auto_invite_threshold ?? 75,
    });
  }

  const handleLaunchMock = async () => {
    setLaunchingMock(true);
    // Open the window synchronously (direct user gesture) — browsers block window.open after await
    const INTERVIEW_URL = import.meta.env.VITE_INTERVIEW_URL || 'http://localhost:5174';
    const newWindow = window.open('', '_blank');
    try {
      const INTERVIEW_API = import.meta.env.VITE_INTERVIEW_API_URL || 'http://localhost:8001';
      const mockResume = `Mock candidate for testing the "${job.title}" interview setup.
Skills: relevant technical and domain knowledge appropriate for this role.
Experience: 5 years of relevant industry experience.`;
      const jd = [job.description, job.requirements, job.responsibilities]
        .filter(Boolean).join('\n\n');
      const res = await fetch(`${INTERVIEW_API}/api/interview/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_description: jd || job.title,
          resume_text: mockResume,
          difficulty: screeningConfig.difficulty,
          seniority_bar: screeningConfig.seniority,
          time_limit: screeningConfig.time_limit,
          num_questions: screeningConfig.num_questions,
          job_id: job.id,
          behavioral_pct: screeningConfig.behavioral_pct ?? 20,
          verify_coding_ability: screeningConfig.verify_coding_ability ?? false,
        }),
      });
      const payload = await res.json();
      if (!res.ok || !payload.session_id) {
        const detail = payload.detail || `Server error (${res.status})`;
        newWindow.close();
        alert(`Could not launch mock interview: ${detail}`);
        return;
      }
      newWindow.location.href = `${INTERVIEW_URL}/interview/${payload.session_id}`;
    } catch (e) {
      console.error('Failed to launch mock interview', e);
      newWindow.close();
      alert('Could not launch mock interview. Check console for details.');
    } finally {
      setLaunchingMock(false);
    }
  };

  const handleSaveScreeningConfig = async () => {
    setSavingConfig(true);
    try {
      await jobsAPI.update(job.id, {
        interview_time_limit: screeningConfig.time_limit,
        interview_num_questions: screeningConfig.num_questions,
        interview_difficulty: screeningConfig.difficulty,
        interview_seniority: screeningConfig.seniority,
        interview_behavioral_pct: screeningConfig.behavioral_pct,
        verify_coding_ability: screeningConfig.verify_coding_ability ?? false,
        auto_invite_screening: screeningConfig.auto_invite_screening,
        auto_invite_threshold: screeningConfig.auto_invite_threshold,
      });

      // Persist video mode toggle to interview module
      await axios.put(`${INTERVIEW_API}/api/interview/job/${job.id}/video-mode`, { enabled: videoModeEnabled });

      // If video mode changed, trigger re-setup with the new video flag so videos get generated (or not)
      if (videoModeEnabled) {
        // Video turned ON — generate videos for existing questions
        await axios.post(`${INTERVIEW_API}/api/interview/job/${job.id}/generate-videos`);
      }

      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 2000);
      // Screening config change triggers re-generation — start polling
      setSetupStatus('generating');
      setSetupProgress({ current: 0, total: screeningConfig.num_questions });
      startSetupPolling(job.id);
    } catch (e) {
      console.error('Failed to save screening config', e);
    } finally {
      setSavingConfig(false);
    }
  };

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
            <Link
              to={`/jobs/${id}/insights`}
              className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors flex items-center gap-2"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              View Insights
            </Link>
            {job.status === 'draft' && (
              <button
                onClick={() => handleJobAction('publish')}
                disabled={setupStatus === 'generating'}
                title={setupStatus === 'generating' ? 'Wait for question generation to complete' : ''}
                className="px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {setupStatus === 'generating' && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
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

      {/* ── Setup Progress Banner ── */}
      {setupStatus === 'generating' && (
        <div className="card p-4 border-amber-200 bg-amber-50">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-amber-600 animate-spin flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800">
                Generating interview questions…
                {setupProgress.total > 0 && ` (${setupProgress.current}/${setupProgress.total})`}
              </p>
              {setupProgress.total > 0 && (
                <div className="mt-2 h-1.5 bg-amber-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.round((setupProgress.current / setupProgress.total) * 100)}%` }}
                  />
                </div>
              )}
              <p className="text-xs text-amber-600 mt-1">Job cannot be published until complete.</p>
            </div>
          </div>
        </div>
      )}
      {setupStatus === 'failed' && (
        <div className="card p-4 border-red-200 bg-red-50">
          <p className="text-sm text-red-700">⚠️ Question generation failed. Save the screening config again to retry.</p>
        </div>
      )}

      {/* ── Pipeline Funnel ── */}
      <PipelineFunnel
        pipeline={pipeline}
        activeStage={funnelStage}
        onStageClick={handleFunnelStageClick}
      />

      {/* ── Stage Filter Strip ── */}
      <StageFilterStrip active={statusFilter} onSelect={handlePillSelect} />

      {/* ── Screening Config ── */}
      <div className="card overflow-hidden">
        <button
          onClick={async () => {
            setShowScreeningConfig(v => !v);
            // Re-fetch questions when panel is opened so they're always fresh
            if (!showScreeningConfig && id) {
              try {
                const sRes = await axios.get(`${INTERVIEW_API}/api/interview/job/${id}/setup/status`);
                const domain = sRes.data.domain || 'all';
                const qRes = await axios.get(`${INTERVIEW_API}/api/interview/question-bank`, {
                  params: { domain, job_id: id, limit: 50 }
                });
                setJobQuestions(qRes.data.questions || []);
              } catch (_) {}
            }
          }}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors"
        >
          <div className="flex items-center gap-2 text-slate-700 font-semibold">
            <Settings className="w-4 h-4 text-slate-500" />
            Screening Interview Config
            {setupStatus === 'generating' && (
              <span className="ml-2 inline-flex items-center gap-1 text-xs font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                <Loader2 className="w-3 h-3 animate-spin" /> Generating…
              </span>
            )}
          </div>
          {showScreeningConfig ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </button>

        {showScreeningConfig && screeningConfig && (
          <div className={`px-6 pb-6 border-t border-slate-100 pt-5 grid grid-cols-1 sm:grid-cols-2 gap-6 ${setupStatus === 'generating' ? 'opacity-50 pointer-events-none select-none' : ''}`}>

            {/* Time limit */}
            <div>
              <label className="flex items-center gap-1.5 text-sm font-medium text-slate-700 mb-2">
                <Clock className="w-4 h-4 text-slate-400" />
                Interview Duration (minutes)
              </label>
              <input
                type="number" min={5} max={180}
                value={screeningConfig.time_limit}
                onChange={e => setScreeningConfig(c => ({ ...c, time_limit: Math.max(5, parseInt(e.target.value) || 5) }))}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>

            {/* Number of questions */}
            <div>
              <label className="flex items-center gap-1.5 text-sm font-medium text-slate-700 mb-2">
                <HelpCircle className="w-4 h-4 text-slate-400" />
                Number of Questions
              </label>
              <input
                type="number" min={1} max={30}
                value={screeningConfig.num_questions}
                onChange={e => setScreeningConfig(c => ({ ...c, num_questions: Math.max(1, parseInt(e.target.value) || 1) }))}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>

            {/* Behavioral split */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-sm font-medium text-slate-700">Behavioral Questions</label>
                <span className="text-sm font-semibold text-slate-700">{screeningConfig.behavioral_pct ?? 20}%</span>
              </div>
              <input
                type="range" min={0} max={50} step={5}
                value={screeningConfig.behavioral_pct ?? 20}
                onChange={e => setScreeningConfig(c => ({ ...c, behavioral_pct: parseInt(e.target.value) }))}
                className="w-full accent-indigo-600"
              />
              <p className="text-xs text-slate-400 mt-1">
                {Math.max(1, Math.round((screeningConfig.num_questions || 8) * (screeningConfig.behavioral_pct ?? 20) / 100))} behavioral · {(screeningConfig.num_questions || 8) - Math.max(1, Math.round((screeningConfig.num_questions || 8) * (screeningConfig.behavioral_pct ?? 20) / 100))} technical (pre-generated, reused across candidates)
              </p>
            </div>

            {/* Difficulty */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">Difficulty</label>
              <div className="grid grid-cols-5 gap-1">
                {[{v:1,l:'Easy'},{v:2,l:'Mod'},{v:3,l:'Std'},{v:4,l:'Hard'},{v:5,l:'Expert'}].map(({v,l}) => (
                  <button
                    key={v}
                    onClick={() => setScreeningConfig(c => ({ ...c, difficulty: v }))}
                    className={`py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                      screeningConfig.difficulty === v
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300'
                    }`}
                  >{l}</button>
                ))}
              </div>
            </div>

            {/* Seniority */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">Seniority Bar</label>
              <div className="grid grid-cols-4 gap-1">
                {[{v:'junior',l:'Junior'},{v:'mid',l:'Mid'},{v:'senior',l:'Senior'},{v:'lead',l:'Lead'}].map(({v,l}) => (
                  <button
                    key={v}
                    onClick={() => setScreeningConfig(c => ({ ...c, seniority: v }))}
                    className={`py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                      screeningConfig.seniority === v
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300'
                    }`}
                  >{l}</button>
                ))}
              </div>
            </div>

            {/* Verify coding ability */}
            <div className="sm:col-span-2">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={screeningConfig.verify_coding_ability ?? false}
                  onChange={e => setScreeningConfig(c => ({ ...c, verify_coding_ability: e.target.checked }))}
                  className="mt-0.5 accent-indigo-600"
                />
                <div>
                  <span className="text-sm font-medium text-slate-700">Verify coding ability</span>
                  <p className="text-xs text-slate-500 mt-0.5">Adds a logic-based coding question to the interview. Candidate can type their solution.</p>
                </div>
              </label>
            </div>

            {/* Core competency questions */}
            {jobQuestions.length > 0 && (
              <div className="sm:col-span-2">
                <label className="text-sm font-medium text-slate-700 mb-2 block">Interview Questions</label>
                <p className="text-xs text-slate-500 mb-2">Flag questions as core competency to add follow-up probes that verify depth of understanding.</p>
                <div className="space-y-1 max-h-56 overflow-y-auto border border-slate-200 rounded-lg p-2">
                  {jobQuestions.map(q => {
                    const isCore = !!q.is_core_competency;
                    return (
                      <div key={q.id} className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-slate-50 text-xs text-slate-600">
                        <button
                          onClick={() => toggleCoreCompetency(q.id, isCore)}
                          className={`flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold border transition-colors ${
                            isCore
                              ? 'bg-amber-100 text-amber-700 border-amber-300 hover:bg-amber-200'
                              : 'bg-slate-50 text-slate-400 border-slate-200 hover:border-amber-300 hover:text-amber-600'
                          }`}
                        >
                          {isCore ? '\u2B50 Core' : 'Mark Core'}
                        </button>
                        <span className="truncate flex-1">{q.question}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Video interview mode toggle */}
            <div className="sm:col-span-2">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-slate-700">Video Interview</span>
                  <p className="text-xs text-slate-500 mt-0.5">Show a recruiter avatar speaking each question. Videos are generated when you save with this enabled.</p>
                </div>
                <button
                  onClick={toggleVideoMode}
                  disabled={setupStatus !== 'ready'}
                  className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none disabled:opacity-50 ${
                    videoModeEnabled ? 'bg-indigo-600' : 'bg-slate-200'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      videoModeEnabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
              {jobQuestions.filter(q => q.video_path).length > 0 && (
                <div className="mt-3 space-y-1 max-h-40 overflow-y-auto">
                  {jobQuestions.filter(q => q.video_path).map(q => (
                    <div key={q.id} className="flex items-center justify-between gap-2 text-xs text-slate-600 py-1.5 border-b border-slate-100 last:border-0">
                      <span className="truncate flex-1">{q.question}</span>
                      <button
                        onClick={() => setVideoPreviewUrl(
                          videoPreviewUrl === `${INTERVIEW_API}/video/${q.video_path}` ? null : `${INTERVIEW_API}/video/${q.video_path}`
                        )}
                        className="text-indigo-600 hover:text-indigo-800 font-medium flex-shrink-0"
                      >
                        Preview
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {videoPreviewUrl && (
                <div className="mt-3 flex justify-center">
                  <video src={videoPreviewUrl} controls autoPlay className="rounded-xl max-h-48 shadow-sm border border-slate-200" />
                </div>
              )}
            </div>

              {/* Screening Automation Toggle */}
            <div className="sm:col-span-2 pt-4 border-t border-slate-100 flex flex-col gap-4">
              <label className="flex items-center gap-3 cursor-pointer select-none">
                <button
                  type="button"
                  role="switch"
                  aria-checked={screeningConfig.auto_invite_screening}
                  onClick={() => setScreeningConfig(c => ({ ...c, auto_invite_screening: !c.auto_invite_screening }))}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    screeningConfig.auto_invite_screening ? 'bg-indigo-600' : 'bg-slate-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      screeningConfig.auto_invite_screening ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-slate-700">Auto-invite to screening</span>
                  <span className="text-xs text-slate-400">Automatically send invites to public applicants meeting the threshold</span>
                </div>
              </label>

              {screeningConfig.auto_invite_screening && (
                <div className="pl-14">
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Minimum resume match score (%)
                  </label>
                  <input
                    type="number" min={1} max={100}
                    value={screeningConfig.auto_invite_threshold}
                    onChange={e => setScreeningConfig(c => ({ ...c, auto_invite_threshold: parseInt(e.target.value) || 75 }))}
                    className="w-28 px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  />
                </div>
              )}
            </div>

            {/* Save + Mock Interview buttons */}
            <div className="sm:col-span-2 flex items-center justify-between pt-2">
              <button
                onClick={handleLaunchMock}
                disabled={launchingMock}
                className="inline-flex items-center gap-2 px-5 py-2 rounded-lg border border-indigo-300 text-indigo-700 bg-indigo-50 text-sm font-semibold hover:bg-indigo-100 disabled:opacity-50 transition-colors"
              >
                {launchingMock ? (
                  <div className="w-4 h-4 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
                ) : (
                  <PlayCircle className="w-4 h-4" />
                )}
                {launchingMock ? 'Launching…' : 'Mock Interview'}
              </button>
              <button
                onClick={handleSaveScreeningConfig}
                disabled={savingConfig}
                className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {savingConfig ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : configSaved ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                {configSaved ? 'Saved!' : 'Save Config'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Candidate Table ── */}
      <div className="card overflow-hidden">
        {/* Header with View Insights button */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Candidates</h2>
          <button
            onClick={() => navigate(`/jobs/${job.id}/insights`)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            📊 View Hiring Insights
          </button>
        </div>
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
                    onViewReport={setReportScreening}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Sticky Bulk Action Bar ── */}
      {selected.size > 0 && (
        <div className="fixed bottom-0 left-0 lg:left-64 right-0 z-40 flex items-center justify-center pb-4 pointer-events-none">
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
      {reportScreening && (
        <ReportModal
          screening={reportScreening}
          onClose={() => setReportScreening(null)}
        />
      )}

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
