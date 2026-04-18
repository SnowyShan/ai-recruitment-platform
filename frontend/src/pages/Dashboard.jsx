import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { dashboardAPI } from '../services/api';
import {
  Briefcase, Users, FileText, CheckCircle2,
  ArrowUpRight, ArrowRight, TrendingDown, Sparkles,
  ChevronRight, MapPin, Building2, Star, Zap, Activity,
  AlertTriangle, AlertCircle
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

/* ── helpers ──────────────────────────────────────────────────────────── */
const PALETTE = [
  'bg-blue-100 text-blue-800','bg-purple-100 text-purple-800',
  'bg-emerald-100 text-emerald-800','bg-amber-100 text-amber-800',
  'bg-pink-100 text-pink-800','bg-teal-100 text-teal-800',
  'bg-indigo-100 text-indigo-800','bg-rose-100 text-rose-800',
];
const Avatar = ({ name, idx = 0 }) => (
  <div className={`w-10 h-10 ${PALETTE[idx % PALETTE.length]} rounded-full flex items-center justify-center font-semibold text-sm flex-shrink-0`}>
    {(name || '?').split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase()}
  </div>
);

const ScoreBadge = ({ score }) => {
  if (score == null) return null;
  const r = Math.round(score);
  const textCls = r >= 80 ? 'text-emerald-600' : r >= 60 ? 'text-amber-600' : 'text-red-500';
  const barCls  = r >= 80 ? 'bg-emerald-500'   : r >= 60 ? 'bg-amber-500'   : 'bg-red-400';
  return (
    <div className="text-right min-w-[52px]">
      <span className={`text-xl font-bold ${textCls}`}>{r}</span>
      <div className="text-xs text-slate-400 mt-0.5">AI match</div>
      <div className="mt-1 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-1.5 rounded-full ${barCls}`} style={{ width: `${r}%` }} />
      </div>
    </div>
  );
};

const STATUS_CLS = {
  pending:'bg-amber-50 text-amber-700 border border-amber-200',
  screening:'bg-blue-50 text-blue-700 border border-blue-200',
  shortlisted:'bg-purple-50 text-purple-700 border border-purple-200',
  interview:'bg-cyan-50 text-cyan-700 border border-cyan-200',
  offered:'bg-emerald-50 text-emerald-700 border border-emerald-200',
  hired:'bg-teal-50 text-teal-800 border border-teal-200',
  rejected:'bg-red-50 text-red-700 border border-red-200',
};
const StatusPill = ({ status }) => (
  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_CLS[status] || 'bg-slate-100 text-slate-600'}`}>
    {status?.replace('_',' ')}
  </span>
);

const MetricCard = ({ label, value, sub, subPositive, icon: Icon, iconBg, iconColor, to }) => {
  const navigate = useNavigate();
  return (
    <div onClick={() => to && navigate(to)}
      className={`card p-5 flex flex-col gap-3 ${to ? 'cursor-pointer hover:shadow-lg hover:-translate-y-0.5 transition-all' : ''}`}>
      <div className="flex items-start justify-between">
        <div className={`w-10 h-10 ${iconBg} rounded-xl flex items-center justify-center`}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
        {to && <ChevronRight className="w-4 h-4 text-slate-300 mt-1" />}
      </div>
      <div>
        <div className="text-2xl font-bold text-slate-900">{typeof value === 'number' ? value.toLocaleString() : (value ?? '—')}</div>
        <div className="text-xs text-slate-500 mt-0.5">{label}</div>
      </div>
      {sub && (
        <div className={`flex items-center gap-1 text-xs font-medium ${subPositive ? 'text-emerald-600' : 'text-red-500'}`}>
          {subPositive ? <ArrowUpRight className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
          {sub}
        </div>
      )}
    </div>
  );
};

const SHead = ({ title, to }) => (
  <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
    <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">{title}</h2>
    {to && <Link to={to} className="text-xs font-medium text-primary-600 hover:text-primary-700 flex items-center gap-1">View all <ArrowRight className="w-3.5 h-3.5" /></Link>}
  </div>
);

const STAGE_COLORS = {
  Applied:'#6366f1','AI Screened':'#8b5cf6',Shortlisted:'#3b82f6',
  Interviewed:'#06b6d4',Offered:'#10b981',Hired:'#059669',
};
const FunnelRow = ({ stage, count, pct }) => (
  <div className="flex items-center gap-4 py-2.5 hover:bg-slate-50 rounded-lg px-2 -mx-2 transition-colors">
    <span className="text-sm text-slate-600 w-28 flex-shrink-0">{stage}</span>
    <div className="w-2.5 h-8 rounded-full flex-shrink-0" style={{ background: STAGE_COLORS[stage] || '#6366f1' }} />
    <span className="text-base font-bold text-slate-900 w-14 flex-shrink-0">{count.toLocaleString()}</span>
    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
      <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: STAGE_COLORS[stage] || '#6366f1' }} />
    </div>
    <span className="text-xs text-slate-400 w-10 text-right flex-shrink-0">{pct > 0 ? `${pct}%` : '—'}</span>
  </div>
);

const InsightCard = ({ insight }) => {
  const bdr = insight.type === 'warn' ? 'border-l-amber-400' : insight.type === 'alert' ? 'border-l-red-400' : 'border-l-primary-400';
  const icon = insight.type === 'warn' ? <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
             : insight.type === 'alert' ? <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
             : <Sparkles className="w-4 h-4 text-primary-500 flex-shrink-0 mt-0.5" />;
  return (
    <div className={`bg-slate-50 rounded-xl p-4 border-l-4 ${bdr}`}>
      <div className="flex items-start gap-2">
        {icon}
        <div className="flex-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">{insight.title}</p>
          <p className="text-sm text-slate-700 leading-relaxed mb-2">{insight.text}</p>
          {insight.action && (
            <Link to={insight.action_to || '/applications'} className="text-xs font-semibold text-primary-600 hover:text-primary-700 flex items-center gap-1">
              {insight.action} <ArrowRight className="w-3 h-3" />
            </Link>
          )}
        </div>
      </div>
    </div>
  );
};

/* ════════════════════════════════════════════════════════════════════════ */
const Dashboard = () => {
  const [stats,        setStats]        = useState(null);
  const [pipeline,     setPipeline]     = useState(null);
  const [funnel,       setFunnel]       = useState(null);
  const [topJobs,      setTopJobs]      = useState([]);
  const [recentApps,   setRecentApps]   = useState([]);
  const [topCandidates,setTopCandidates]= useState([]);
  const [scrPerf,      setScrPerf]      = useState(null);
  const [insights,     setInsights]     = useState([]);
  const [weeklyTrend,  setWeeklyTrend]  = useState([]);
  const [loading,      setLoading]      = useState(true);

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    try {
      const [statsR, pipeR, funnelR, jobsR, appsR, candR, scrR, insR, trendR] = await Promise.all([
        dashboardAPI.getStats(),
        dashboardAPI.getPipelineOverview(),
        dashboardAPI.getHiringFunnel(),
        dashboardAPI.getTopJobs({ limit: 5 }),
        dashboardAPI.getRecentApplications({ limit: 5 }),
        dashboardAPI.getTopCandidates({ limit: 4 }),
        dashboardAPI.getScreeningPerformance({ days: 30 }),
        dashboardAPI.getInsights(),
        dashboardAPI.getWeeklyTrend({ weeks: 8 }),
      ]);
      setStats(statsR.data); setPipeline(pipeR.data); setFunnel(funnelR.data);
      setTopJobs(jobsR.data); setRecentApps(appsR.data); setTopCandidates(candR.data);
      setScrPerf(scrR.data); setInsights(insR.data.insights || []);
      setWeeklyTrend(trendR.data.trend || []);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="spinner" /></div>;

  const totalApps  = stats?.total_applications || 0;
  const funnelData = funnel?.funnel || [];
  const scrComplete = scrPerf?.completed || 0;
  const avgScore   = scrPerf?.average_overall_score || 0;

  return (
    <div className="space-y-6 animate-fade-in pb-8">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Recruitment Dashboard</h1>
          <p className="text-slate-500 text-sm mt-0.5">Real-time hiring overview</p>
        </div>
        <select className="input py-2 w-auto text-sm">
          <option>Last 30 days</option><option>Last 7 days</option><option>Last 90 days</option>
        </select>
      </div>

      {/* ── Row 1: 6 metric cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
        <MetricCard label="Vacancies"       value={stats?.active_jobs}         sub={`${stats?.total_jobs} total jobs`}    subPositive icon={Briefcase}    iconBg="bg-blue-50"    iconColor="text-blue-600"    to="/jobs" />
        <MetricCard label="Applications"    value={totalApps}                  sub="All-time submissions"                 subPositive icon={FileText}     iconBg="bg-indigo-50"  iconColor="text-indigo-600"  to="/applications" />
        <MetricCard label="Shortlisted"     value={pipeline?.shortlisted}      sub={`${totalApps > 0 ? Math.round(((pipeline?.shortlisted||0)/totalApps)*100) : 0}% of applicants`} subPositive icon={Star} iconBg="bg-purple-50" iconColor="text-purple-600" to="/applications" />
        <MetricCard label="AI Screened"     value={pipeline?.screening}        sub={`${scrComplete} completed`}           subPositive icon={Sparkles}     iconBg="bg-violet-50"  iconColor="text-violet-600"  to="/screenings" />
        <MetricCard label="Interview Phase" value={pipeline?.interview}        sub="In final rounds"                      subPositive icon={Users}        iconBg="bg-cyan-50"    iconColor="text-cyan-600"    to="/candidates" />
        <MetricCard label="Hired"           value={stats?.hired_count}         sub="Successful placements"                subPositive icon={CheckCircle2} iconBg="bg-emerald-50" iconColor="text-emerald-600" to="/applications" />
      </div>

      {/* ── Row 2: Active Requisitions + Top AI-Matched Candidates ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Requisitions */}
        <div className="card overflow-hidden">
          <SHead title="Active Requisitions" to="/jobs" />
          <div className="divide-y divide-slate-50">
            {topJobs.length > 0 ? topJobs.map((job) => (
              <Link key={job.id} to={`/jobs/${job.id}`}
                className="flex items-center gap-4 px-6 py-3.5 hover:bg-slate-50 transition-colors group">
                <div className="w-9 h-9 bg-slate-100 rounded-xl flex items-center justify-center flex-shrink-0 group-hover:bg-primary-50 transition-colors">
                  <Briefcase className="w-4 h-4 text-slate-500 group-hover:text-primary-600 transition-colors" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold text-slate-900 truncate">{job.title}</p>
                    {job.is_urgent && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-red-50 text-red-600 border border-red-200 rounded text-[10px] font-bold uppercase tracking-wide flex-shrink-0">
                        <AlertTriangle className="w-2.5 h-2.5" /> Urgent
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    {job.department && <span className="text-xs text-slate-400 flex items-center gap-1"><Building2 className="w-3 h-3" />{job.department}</span>}
                    {job.location   && <span className="text-xs text-slate-400 flex items-center gap-1"><MapPin className="w-3 h-3" />{job.location}</span>}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className={`text-sm font-bold ${job.is_urgent ? 'text-red-500' : job.applications_count < 6 ? 'text-amber-500' : 'text-primary-600'}`}>
                    {job.applications_count} candidates
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{job.days_open ?? 0}d open</div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors flex-shrink-0" />
              </Link>
            )) : (
              <div className="p-8 text-center text-slate-400">
                <Briefcase className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No active jobs</p>
              </div>
            )}
          </div>
        </div>

        {/* Top AI-Matched Candidates */}
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Top AI-Matched Candidates</h2>
            <span className="text-xs bg-purple-100 text-purple-700 font-semibold px-2.5 py-1 rounded-full">AI scored</span>
          </div>
          <div className="divide-y divide-slate-50">
            {topCandidates.length > 0 ? topCandidates.map((c, i) => (
              <Link key={c.id} to="/applications" className="flex items-center gap-4 px-6 py-3.5 hover:bg-slate-50 transition-colors">
                <Avatar name={c.candidate_name} idx={i} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-900 truncate">{c.candidate_name}</p>
                  <p className="text-xs text-slate-400 mt-0.5 truncate">{c.job_title}</p>
                  <div className="mt-1 flex items-center gap-2 flex-wrap">
                    <StatusPill status={c.status} />
                    {c.experience_years != null && <span className="text-xs text-slate-400">{c.experience_years} yrs</span>}
                  </div>
                </div>
                <ScoreBadge score={c.match_score} />
              </Link>
            )) : (
              <div className="p-8 text-center text-slate-400">
                <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No scored candidates yet</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Row 3: Candidate Pipeline funnel + Recent Screenings ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Candidate Pipeline */}
        <div className="card overflow-hidden">
          <SHead title="Candidate Pipeline" to="/applications" />
          <div className="px-6 py-4">
            {funnelData.length > 0 ? funnelData.map(s => (
              <FunnelRow key={s.stage} stage={s.stage} count={s.count} pct={s.percentage} />
            )) : <div className="py-8 text-center text-slate-400 text-sm">No pipeline data</div>}
          </div>
        </div>

        {/* Recent Screenings */}
        <div className="card overflow-hidden">
          <SHead title="Today's Screenings" to="/screenings" />
          <div className="px-6 py-3 space-y-3">
            {recentApps.length > 0 ? recentApps.slice(0,4).map((app, i) => {
              const tags = ['AI Technical','Panel','Final Round','Culture Fit','Screening'];
              const tagColors = [
                'text-blue-700 bg-blue-50 border-blue-200',
                'text-purple-700 bg-purple-50 border-purple-200',
                'text-amber-700 bg-amber-50 border-amber-200',
                'text-teal-700 bg-teal-50 border-teal-200',
                'text-indigo-700 bg-indigo-50 border-indigo-200',
              ];
              return (
                <Link key={app.id} to="/screenings"
                  className="flex items-start gap-3 p-3 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors group">
                  <div className="w-10 text-xs font-semibold text-slate-400 pt-0.5 flex-shrink-0">
                    {['10:00','11:30','14:00','15:30'][i]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-900">{app.candidate_name}</p>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">{app.job_title}</p>
                    <span className={`inline-block mt-1.5 text-xs font-medium px-2 py-0.5 rounded border ${tagColors[i%tagColors.length]}`}>
                      {tags[i%tags.length]}
                    </span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 mt-0.5 flex-shrink-0" />
                </Link>
              );
            }) : <div className="py-8 text-center text-slate-400 text-sm">No screenings yet</div>}
          </div>
        </div>
      </div>

      {/* ── Row 4: Trend chart + AI Insights ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Weekly trend */}
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Applications Trend</h2>
              <p className="text-xs text-slate-400 mt-0.5">Weekly inflow — last 8 weeks</p>
            </div>
            <Link to="/applications" className="text-xs font-medium text-primary-600 flex items-center gap-1">Details <ArrowRight className="w-3.5 h-3.5" /></Link>
          </div>
          <div className="px-6 py-4">
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={weeklyTrend} margin={{ top:4, right:4, left:-22, bottom:0 }}>
                  <defs>
                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.18}/>
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9"/>
                  <XAxis dataKey="label" tick={{ fill:'#94a3b8', fontSize:11 }}/>
                  <YAxis tick={{ fill:'#94a3b8', fontSize:11 }}/>
                  <Tooltip contentStyle={{ background:'white', border:'1px solid #e2e8f0', borderRadius:'10px', fontSize:12 }} formatter={v=>[v,'Applications']}/>
                  <Area type="monotone" dataKey="applications" stroke="#6366f1" strokeWidth={2} fill="url(#areaGrad)" dot={{ r:3, fill:'#6366f1' }} activeDot={{ r:5 }}/>
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-slate-100">
              {[
                { label:'Avg AI score',    value: avgScore > 0 ? `${Math.round(avgScore)}/100` : '—', color:'text-purple-600' },
                { label:'Screenings done', value: scrComplete, color:'text-blue-600' },
                { label:'Pending review',  value: stats?.pending_applications || 0, color:'text-amber-600' },
              ].map(({ label, value, color }) => (
                <div key={label} className="text-center">
                  <div className={`text-xl font-bold ${color}`}>{value}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* AI Insights */}
        <div className="card overflow-hidden">
          <div className="flex items-center gap-2 px-6 py-4 border-b border-slate-100">
            <div className="w-7 h-7 bg-purple-100 rounded-lg flex items-center justify-center">
              <Zap className="w-4 h-4 text-purple-600"/>
            </div>
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">AI Recruitment Insights</h2>
          </div>
          <div className="px-6 py-5 space-y-3">
            {insights.length > 0 ? insights.map((ins,i) => (
              <InsightCard key={i} insight={ins}/>
            )) : (
              <div className="py-6 text-center text-slate-400">
                <Activity className="w-8 h-8 mx-auto mb-2 opacity-40"/>
                <p className="text-sm">Your pipeline looks healthy!</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Row 5: Recent Applications ── */}
      <div className="card overflow-hidden">
        <SHead title="Recent Applications" to="/applications"/>
        <div className="divide-y divide-slate-50">
          {recentApps.length > 0 ? recentApps.map((app,i) => (
            <Link key={app.id} to="/applications"
              className="flex items-center gap-4 px-6 py-3 hover:bg-slate-50 transition-colors">
              <Avatar name={app.candidate_name} idx={i+4}/>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-900 truncate">{app.candidate_name}</p>
                <p className="text-xs text-slate-400 truncate">{app.job_title}</p>
              </div>
              <div className="text-right flex-shrink-0">
                {app.match_score != null
                  ? <div className={`text-sm font-bold mb-0.5 ${app.match_score>=80?'text-emerald-600':app.match_score>=60?'text-amber-600':'text-red-500'}`}>{Math.round(app.match_score)}%</div>
                  : <div className="text-xs text-slate-400 mb-0.5">No score</div>}
                <StatusPill status={app.status}/>
              </div>
            </Link>
          )) : (
            <div className="p-8 text-center text-slate-400">
              <FileText className="w-10 h-10 mx-auto mb-2 opacity-30"/>
              <p className="text-sm">No applications yet</p>
            </div>
          )}
        </div>
      </div>

    </div>
  );
};

export default Dashboard;
