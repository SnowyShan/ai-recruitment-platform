import { useState, useEffect } from 'react';
import { screeningsAPI, applicationsAPI } from '../services/api';
import {
  MessageSquare, Plus, Search, ChevronDown, ChevronUp,
  CheckCircle, XCircle, Eye, Sparkles, X,
  Briefcase, Users, MapPin, Building2, AlertCircle,
  Mail, RotateCcw
} from 'lucide-react';

/* ─── helpers ─────────────────────────────────────────────────────────────── */
const statusConfig = {
  scheduled:   { label: 'Scheduled',   bg: 'bg-blue-100',    text: 'text-blue-700',    dot: 'bg-blue-500'   },
  in_progress: { label: 'In Progress', bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500'  },
  completed:   { label: 'Completed',   bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500'},
  cancelled:   { label: 'Cancelled',   bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500'    },
};

const StatusBadge = ({ status }) => {
  const cfg = statusConfig[status] || statusConfig.scheduled;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.bg} ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
};

const ScorePill = ({ score }) => {
  if (score == null) return <span className="text-slate-400 text-sm">—</span>;
  const r = Math.round(score);
  const c = r >= 80 ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
          : r >= 60 ? 'bg-amber-50 text-amber-700 ring-amber-200'
          :           'bg-red-50 text-red-700 ring-red-200';
  return <span className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-bold ring-2 ${c}`}>{r}</span>;
};

const RecBadge = ({ rec }) => {
  if (!rec) return null;
  const pass = rec === 'pass' || rec === 'strong_yes' || rec === 'yes';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${pass ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
      {pass ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      {pass ? 'Recommended' : 'Not Recommended'}
    </span>
  );
};

const Avatar = ({ name }) => {
  const initials = (name || '?').split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase();
  const colors = ['bg-blue-500','bg-purple-500','bg-pink-500','bg-indigo-500','bg-teal-500'];
  return (
    <div className={`w-9 h-9 ${colors[initials.charCodeAt(0) % colors.length]} rounded-full flex items-center justify-center text-white text-sm font-semibold flex-shrink-0`}>
      {initials}
    </div>
  );
};

/* ─── Detail drawer ───────────────────────────────────────────────────────── */
const ScreeningDrawer = ({ screening, onClose, onAction }) => {
  const [busy, setBusy] = useState(false);

  const act = async (action) => {
    setBusy(true);
    try {
      if (action === 'cancel')   await screeningsAPI.cancel(screening.id);
      if (action === 'complete') await screeningsAPI.complete(screening.id);
      onAction(); onClose();
    } catch(e) { console.error(e); } finally { setBusy(false); }
  };

  let ev = null;
  try { ev = screening.ai_evaluation ? JSON.parse(screening.ai_evaluation) : null; } catch {}

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex justify-end" onClick={onClose}>
      <div className="w-full max-w-lg bg-white h-full overflow-y-auto shadow-2xl animate-slide-in-right" onClick={e => e.stopPropagation()}>
        <div className="sticky top-0 bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Screening Report</h2>
            <p className="text-sm text-slate-500">{screening.candidate?.full_name}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-6 space-y-6">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <StatusBadge status={screening.status} />
            <RecBadge rec={screening.recommendation} />
          </div>

          {screening.status === 'completed' && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Overall',       score: screening.overall_score },
                { label: 'Technical',     score: screening.technical_score },
                { label: 'Communication', score: screening.communication_score },
                { label: 'Cultural Fit',  score: screening.cultural_fit_score },
              ].map(({ label, score }) => (
                <div key={label} className="bg-slate-50 rounded-xl p-4 flex items-center gap-4">
                  <ScorePill score={score} />
                  <div>
                    <div className="text-xs text-slate-500">{label}</div>
                    <div className="text-sm font-semibold text-slate-800">{score != null ? `${Math.round(score)}/100` : 'N/A'}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {ev?.summary && (
            <div className="bg-purple-50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-semibold text-purple-900">AI Summary</span>
              </div>
              <p className="text-sm text-purple-800 leading-relaxed">{ev.summary}</p>
            </div>
          )}

          {(ev?.strengths?.length > 0 || ev?.weaknesses?.length > 0) && (
            <div className="grid grid-cols-2 gap-4">
              {ev.strengths?.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-emerald-700 uppercase tracking-wide mb-2">Strengths</h4>
                  <ul className="space-y-1">
                    {ev.strengths.map((s,i) => (
                      <li key={i} className="text-sm text-slate-700 flex items-start gap-1.5">
                        <CheckCircle className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />{s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {ev?.weaknesses?.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-red-700 uppercase tracking-wide mb-2">Areas to Improve</h4>
                  <ul className="space-y-1">
                    {ev.weaknesses.map((w,i) => (
                      <li key={i} className="text-sm text-slate-700 flex items-start gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 flex-shrink-0" />{w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="bg-slate-50 rounded-xl p-4 space-y-2">
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Timeline</h4>
            {screening.scheduled_at && <div className="flex justify-between text-sm"><span className="text-slate-500">Invited</span><span className="text-slate-900">{new Date(screening.scheduled_at).toLocaleString()}</span></div>}
            {screening.completed_at && <div className="flex justify-between text-sm"><span className="text-slate-500">Completed</span><span className="text-slate-900">{new Date(screening.completed_at).toLocaleString()}</span></div>}
            <div className="flex justify-between text-sm"><span className="text-slate-500">Invite used</span><span className={screening.invite_used ? 'text-emerald-600' : 'text-amber-600'}>{screening.invite_used ? 'Yes' : 'Not yet'}</span></div>
          </div>

          <div className="flex gap-3 pt-1">
            {screening.status === 'scheduled' && (
              <button onClick={() => act('cancel')} disabled={busy} className="flex-1 btn btn-secondary flex items-center justify-center gap-2 py-2.5">
                <XCircle className="w-4 h-4" /> Cancel
              </button>
            )}
            {screening.status === 'in_progress' && (
              <button onClick={() => act('complete')} disabled={busy} className="flex-1 btn btn-success flex items-center justify-center gap-2 py-2.5">
                <CheckCircle className="w-4 h-4" /> Mark Complete
              </button>
            )}
            {screening.interview_session_id && (
              <a
                href={`${import.meta.env.VITE_INTERVIEW_URL || 'http://localhost:5174'}/report/${screening.interview_session_id}`}
                target="_blank" rel="noreferrer"
                className="flex-1 btn btn-primary flex items-center justify-center gap-2 py-2.5"
              >
                <Eye className="w-4 h-4" /> View Full Report
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

/* ─── Candidate row ───────────────────────────────────────────────────────── */
const CandidateRow = ({ s, onSelect, onReinvite }) => (
  <div className="flex items-center gap-4 px-4 py-3 hover:bg-slate-50 rounded-xl transition-colors">
    <Avatar name={s.candidate?.full_name} />
    <div className="flex-1 min-w-0">
      <p className="text-sm font-semibold text-slate-900 truncate">{s.candidate?.full_name || 'Unknown'}</p>
      <p className="text-xs text-slate-500 truncate">{s.candidate?.email}</p>
    </div>
    <div className="w-12 text-center"><ScorePill score={s.overall_score} /></div>
    <div className="w-32 flex-shrink-0"><StatusBadge status={s.status} /></div>
    <div className="w-36 flex-shrink-0 hidden lg:block"><RecBadge rec={s.recommendation} /></div>
    <div className="flex items-center gap-1 flex-shrink-0">
      <button onClick={() => onSelect(s)} className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100" title="View details">
        <Eye className="w-4 h-4" />
      </button>
      {(s.status === 'cancelled' || s.status === 'completed') && (
        <button onClick={() => onReinvite(s.application_id)} className="p-2 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50" title="Re-invite">
          <RotateCcw className="w-4 h-4" />
        </button>
      )}
    </div>
  </div>
);

/* ─── Job accordion card ──────────────────────────────────────────────────── */
const JobCard = ({ group, onSelect, onReinvite }) => {
  const [open, setOpen] = useState(true);
  const [sortStatus, setSortStatus] = useState('');
  const allSs = group.screenings;
  const ss = sortStatus ? allSs.filter(s => s.status === sortStatus) : allSs;
  const counts = {
    scheduled:   allSs.filter(s => s.status === 'scheduled').length,
    in_progress: allSs.filter(s => s.status === 'in_progress').length,
    completed:   allSs.filter(s => s.status === 'completed').length,
    cancelled:   allSs.filter(s => s.status === 'cancelled').length,
  };

  return (
    <div className="card overflow-hidden">
      <button
        className="w-full flex items-center gap-4 px-6 py-4 hover:bg-slate-50 transition-colors text-left"
        onClick={() => setOpen(o => !o)}
      >
        <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center flex-shrink-0">
          <Briefcase className="w-5 h-5 text-indigo-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-slate-900">{group.job_title}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${group.job_status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
              {group.job_status}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-0.5 flex-wrap">
            {group.job_department && <span className="text-xs text-slate-500 flex items-center gap-1"><Building2 className="w-3 h-3" />{group.job_department}</span>}
            {group.job_location   && <span className="text-xs text-slate-500 flex items-center gap-1"><MapPin className="w-3 h-3" />{group.job_location}</span>}
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-3 flex-shrink-0">
          <div className="flex items-center gap-1.5 text-sm text-slate-600">
            <Users className="w-4 h-4 text-slate-400" />
            <span className="font-semibold">{ss.length}</span>
            <span className="text-slate-400">candidate{ss.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="flex gap-1.5">
            {counts.scheduled   > 0 && <span className="text-xs bg-blue-100 text-blue-700 rounded-full px-2 py-0.5">{counts.scheduled} pending</span>}
            {counts.in_progress > 0 && <span className="text-xs bg-amber-100 text-amber-700 rounded-full px-2 py-0.5">{counts.in_progress} live</span>}
            {counts.completed   > 0 && <span className="text-xs bg-emerald-100 text-emerald-700 rounded-full px-2 py-0.5">{counts.completed} done</span>}
          </div>
        </div>
        <div className="flex-shrink-0 ml-2">
          {open ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-slate-100">
          <div className="flex items-center gap-4 px-4 py-2 bg-slate-50 text-xs font-medium text-slate-500 uppercase tracking-wide">
            <div className="w-9 flex-shrink-0" />
            <div className="flex-1">Candidate</div>
            <div className="w-12 text-center">Score</div>
            <div className="w-32 flex-shrink-0">Status</div>
            <div className="w-36 flex-shrink-0 hidden lg:block">Result</div>
            <div className="w-16 flex-shrink-0" />
          </div>
          <div className="divide-y divide-slate-50 px-2">
            {ss.map(s => (
              <CandidateRow key={s.id} s={s} onSelect={onSelect} onReinvite={onReinvite} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/* ─── Create/re-invite modal ──────────────────────────────────────────────── */
const CreateModal = ({ applications, preselectedAppId, onClose, onSuccess }) => {
  const [appId, setAppId] = useState(preselectedAppId?.toString() || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await screeningsAPI.create({ application_id: parseInt(appId) });
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to schedule screening');
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg animate-in">
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900">{preselectedAppId ? 'Re-invite Candidate' : 'Schedule AI Screening'}</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={submit} className="p-6 space-y-5">
          {error && <div className="p-3 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm flex items-start gap-2"><AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />{error}</div>}
          <div>
            <label className="label">Shortlisted Application *</label>
            <select value={appId} onChange={e => setAppId(e.target.value)} className="input" required>
              <option value="">Choose a candidate…</option>
              {applications.map(a => (
                <option key={a.id} value={a.id}>{a.candidate?.full_name} — {a.job?.title}</option>
              ))}
            </select>
            {applications.length === 0 && (
              <p className="text-sm text-amber-600 mt-2 flex items-center gap-1"><AlertCircle className="w-4 h-4" />No shortlisted applications. Shortlist candidates first.</p>
            )}
          </div>
          <div className="p-4 bg-purple-50 rounded-xl">
            <div className="flex items-center gap-2 mb-1.5"><Sparkles className="w-4 h-4 text-purple-600" /><span className="text-sm font-semibold text-purple-900">AI-Powered Screening</span></div>
            <p className="text-sm text-purple-700">An automated voice interview link will be emailed to the candidate. Claude AI evaluates their technical skills, communication and cultural fit.</p>
          </div>
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={loading || !appId} className="btn btn-primary flex-1 flex items-center justify-center gap-2">
              <Mail className="w-4 h-4" />{loading ? 'Sending invite…' : preselectedAppId ? 'Re-send Invite' : 'Schedule & Invite'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

/* ─── Main page ───────────────────────────────────────────────────────────── */
const Screenings = () => {
  const [jobGroups, setJobGroups] = useState([]);
  const [filtered, setFiltered]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [search, setSearch]       = useState('');
  const [statusFilter, setStatus] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [reinviteApp, setReinvite]= useState(null);
  const [selected, setSelected]   = useState(null);
  const [apps, setApps]           = useState([]);

  useEffect(() => { loadData(); }, []);

  useEffect(() => {
    let groups = jobGroups;
    if (search.trim()) {
      const q = search.toLowerCase();
      groups = groups.map(g => ({ ...g, screenings: g.screenings.filter(s => s.candidate?.full_name?.toLowerCase().includes(q) || g.job_title.toLowerCase().includes(q)) })).filter(g => g.screenings.length > 0);
    }
    if (statusFilter) {
      groups = groups.map(g => ({ ...g, screenings: g.screenings.filter(s => s.status === statusFilter) })).filter(g => g.screenings.length > 0);
    }
    setFiltered(groups);
  }, [search, statusFilter, jobGroups]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [byJobRes, appsRes] = await Promise.all([
        screeningsAPI.getByJob(),
        applicationsAPI.getAll({ status: 'shortlisted' }),
      ]);
      setJobGroups(byJobRes.data);
      setApps(appsRes.data);
    } catch(e) { console.error(e); } finally { setLoading(false); }
  };

  const all = jobGroups.flatMap(g => g.screenings);
  const stats = [
    { key: 'scheduled',   label: 'Scheduled',   n: all.filter(s=>s.status==='scheduled').length,   color:'bg-blue-500',    light:'bg-blue-50',    text:'text-blue-700'    },
    { key: 'in_progress', label: 'In Progress', n: all.filter(s=>s.status==='in_progress').length, color:'bg-amber-500',   light:'bg-amber-50',   text:'text-amber-700'   },
    { key: 'completed',   label: 'Completed',   n: all.filter(s=>s.status==='completed').length,   color:'bg-emerald-500', light:'bg-emerald-50', text:'text-emerald-700' },
    { key: 'cancelled',   label: 'Cancelled',   n: all.filter(s=>s.status==='cancelled').length,   color:'bg-red-500',     light:'bg-red-50',     text:'text-red-700'     },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">AI Screenings</h1>
          <p className="text-slate-500 mt-1">Candidates grouped by job — scores, status and reports</p>
        </div>
        <button onClick={() => { setReinvite(null); setShowModal(true); }} className="btn btn-primary">
          <Plus className="w-4 h-4" /> Schedule Screening
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(s => (
          <button key={s.key}
            onClick={() => setStatus(p => p === s.key ? '' : s.key)}
            className={`card p-4 text-left transition-all hover:shadow-md ${statusFilter === s.key ? `ring-2 ring-offset-1 ${s.text.replace('text','ring')}` : ''}`}
          >
            <div className={`w-8 h-8 ${s.light} rounded-lg flex items-center justify-center mb-2`}>
              <div className={`w-3 h-3 rounded-full ${s.color}`} />
            </div>
            <div className={`text-2xl font-bold ${s.text}`}>{s.n}</div>
            <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
          </button>
        ))}
      </div>

      {/* Search + filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input type="text" placeholder="Search by job title or candidate name…" value={search} onChange={e => setSearch(e.target.value)} className="input pl-10 w-full" />
        </div>
        <select value={statusFilter} onChange={e => setStatus(e.target.value)} className="input w-auto min-w-[160px]">
          <option value="">All Statuses</option>
          <option value="scheduled">Scheduled</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Job groups */}
      {loading ? (
        <div className="flex items-center justify-center h-48"><div className="spinner" /></div>
      ) : filtered.length > 0 ? (
        <div className="space-y-4">
          {filtered.map(g => (
            <JobCard key={g.job_id} group={g} onSelect={setSelected} onReinvite={id => { setReinvite(id); setShowModal(true); }} />
          ))}
        </div>
      ) : (
        <div className="card p-12 text-center">
          <MessageSquare className="w-16 h-16 mx-auto mb-4 text-slate-300" />
          <h3 className="text-xl font-semibold text-slate-900 mb-2">
            {search || statusFilter ? 'No matching screenings' : 'No screenings yet'}
          </h3>
          <p className="text-slate-500 mb-6">
            {search || statusFilter ? 'Try adjusting your filters.' : 'Schedule an AI screening to see candidates grouped by job here.'}
          </p>
          {!search && !statusFilter && (
            <button onClick={() => setShowModal(true)} className="btn btn-primary"><Plus className="w-4 h-4" /> Schedule Screening</button>
          )}
        </div>
      )}

      {selected && <ScreeningDrawer screening={selected} onClose={() => setSelected(null)} onAction={() => { loadData(); setSelected(null); }} />}
      {showModal && <CreateModal applications={apps} preselectedAppId={reinviteApp} onClose={() => { setShowModal(false); setReinvite(null); }} onSuccess={() => { setShowModal(false); setReinvite(null); loadData(); }} />}
    </div>
  );
};

export default Screenings;
