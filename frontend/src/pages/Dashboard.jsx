import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { dashboardAPI, applicationsAPI } from '../services/api';
import {
  Briefcase,
  Users,
  FileText,
  TrendingUp,
  Clock,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  ArrowRight,
  Sparkles,
  Calendar,
  Target,
  Zap,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [recentApplications, setRecentApplications] = useState([]);
  const [topJobs, setTopJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const [statsRes, pipelineRes, appsRes, jobsRes] = await Promise.all([
        dashboardAPI.getStats(),
        dashboardAPI.getPipelineOverview(),
        dashboardAPI.getRecentApplications({ limit: 5 }),
        dashboardAPI.getTopJobs({ limit: 5 }),
      ]);
      
      setStats(statsRes.data);
      setPipeline(pipelineRes.data);
      setRecentApplications(appsRes.data);
      setTopJobs(jobsRes.data);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      label: 'Total Jobs',
      value: stats?.total_jobs || 0,
      change: '+12%',
      positive: true,
      icon: Briefcase,
      color: 'bg-blue-500',
      bgColor: 'bg-blue-50',
    },
    {
      label: 'Active Jobs',
      value: stats?.active_jobs || 0,
      change: '+5',
      positive: true,
      icon: Target,
      color: 'bg-emerald-500',
      bgColor: 'bg-emerald-50',
    },
    {
      label: 'Total Candidates',
      value: stats?.total_candidates || 0,
      change: '+23%',
      positive: true,
      icon: Users,
      color: 'bg-purple-500',
      bgColor: 'bg-purple-50',
    },
    {
      label: 'Applications',
      value: stats?.total_applications || 0,
      change: '+18%',
      positive: true,
      icon: FileText,
      color: 'bg-amber-500',
      bgColor: 'bg-amber-50',
    },
    {
      label: 'Pending Review',
      value: stats?.pending_applications || 0,
      change: '-8',
      positive: false,
      icon: Clock,
      color: 'bg-orange-500',
      bgColor: 'bg-orange-50',
    },
    {
      label: 'Hired',
      value: stats?.hired_count || 0,
      change: '+3',
      positive: true,
      icon: CheckCircle2,
      color: 'bg-teal-500',
      bgColor: 'bg-teal-50',
    },
  ];

  const pipelineData = pipeline ? [
    { name: 'Pending', value: pipeline.pending, color: '#f59e0b' },
    { name: 'Screening', value: pipeline.screening, color: '#8b5cf6' },
    { name: 'Shortlisted', value: pipeline.shortlisted, color: '#3b82f6' },
    { name: 'Interview', value: pipeline.interview, color: '#06b6d4' },
    { name: 'Offered', value: pipeline.offered, color: '#10b981' },
    { name: 'Hired', value: pipeline.hired, color: '#059669' },
  ] : [];

  const getScoreColor = (score) => {
    if (score >= 80) return 'score-high';
    if (score >= 60) return 'score-medium';
    return 'score-low';
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: 'badge-warning',
      screening: 'badge-info',
      shortlisted: 'badge-primary',
      interview: 'badge-info',
      offered: 'badge-success',
      hired: 'badge-success',
      rejected: 'badge-danger',
    };
    return styles[status] || 'badge-secondary';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-500 mt-1">Welcome back! Here's what's happening with your hiring.</p>
        </div>
        <div className="flex items-center gap-3">
          <select className="input py-2 w-auto">
            <option>Last 7 days</option>
            <option>Last 30 days</option>
            <option>Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-5">
        {statCards.map((stat, index) => (
          <div key={index} className="stat-card group hover:scale-[1.02] transition-transform">
            <div className={`w-12 h-12 ${stat.bgColor} rounded-xl flex items-center justify-center mb-4`}>
              <stat.icon className={`w-6 h-6 ${stat.color.replace('bg-', 'text-')}`} />
            </div>
            <div className="text-3xl font-bold text-slate-900 mb-1">
              {stat.value.toLocaleString()}
            </div>
            <div className="text-sm text-slate-500 mb-2">{stat.label}</div>
            <div className={`inline-flex items-center gap-1 text-xs font-medium ${stat.positive ? 'text-emerald-600' : 'text-red-600'}`}>
              {stat.positive ? <ArrowUpRight className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
              {stat.change} this month
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pipeline Overview */}
        <div className="lg:col-span-2 card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Hiring Pipeline</h2>
            <Link to="/applications" className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="card-body">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pipelineData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" tick={{ fill: '#64748b', fontSize: 12 }} />
                  <YAxis dataKey="name" type="category" tick={{ fill: '#64748b', fontSize: 12 }} width={80} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'white', 
                      border: '1px solid #e2e8f0',
                      borderRadius: '12px',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                    }} 
                  />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                    {pipelineData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-slate-900">Quick Actions</h2>
          </div>
          <div className="card-body space-y-3">
            <Link to="/jobs/new" className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white hover:from-primary-600 hover:to-primary-700 transition-all group">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                <Briefcase className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <div className="font-medium">Post New Job</div>
                <div className="text-sm text-white/70">Create a new job posting</div>
              </div>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link to="/candidates" className="flex items-center gap-4 p-4 rounded-xl bg-slate-50 hover:bg-slate-100 transition-all group">
              <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                <Users className="w-5 h-5 text-emerald-600" />
              </div>
              <div className="flex-1">
                <div className="font-medium text-slate-900">Add Candidate</div>
                <div className="text-sm text-slate-500">Import or add manually</div>
              </div>
              <ArrowRight className="w-5 h-5 text-slate-400 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link to="/screenings" className="flex items-center gap-4 p-4 rounded-xl bg-slate-50 hover:bg-slate-100 transition-all group">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-purple-600" />
              </div>
              <div className="flex-1">
                <div className="font-medium text-slate-900">AI Screening</div>
                <div className="text-sm text-slate-500">Start automated interviews</div>
              </div>
              <ArrowRight className="w-5 h-5 text-slate-400 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link to="/applications" className="flex items-center gap-4 p-4 rounded-xl bg-slate-50 hover:bg-slate-100 transition-all group">
              <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                <FileText className="w-5 h-5 text-amber-600" />
              </div>
              <div className="flex-1">
                <div className="font-medium text-slate-900">Review Applications</div>
                <div className="text-sm text-slate-500">{stats?.pending_applications || 0} pending</div>
              </div>
              <ArrowRight className="w-5 h-5 text-slate-400 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Applications & Top Jobs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Applications */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Recent Applications</h2>
            <Link to="/applications" className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100">
            {recentApplications.length > 0 ? (
              recentApplications.map((app, index) => (
                <div key={index} className="p-4 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-gradient-to-br from-slate-200 to-slate-300 rounded-full flex items-center justify-center text-slate-600 font-medium">
                      {app.candidate_name?.charAt(0)?.toUpperCase() || '?'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-slate-900 truncate">{app.candidate_name}</div>
                      <div className="text-sm text-slate-500 truncate">{app.job_title}</div>
                    </div>
                    <div className="text-right">
                      {app.match_score != null
                        ? <div className={`score-badge ${getScoreColor(app.match_score)} mb-1`}>{Math.round(app.match_score)}%</div>
                        : <span className="text-xs text-slate-400 block mb-1">No resume</span>
                      }
                      <span className={`badge ${getStatusBadge(app.status)}`}>
                        {app.status}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-slate-500">
                <FileText className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                <p>No recent applications</p>
              </div>
            )}
          </div>
        </div>

        {/* Top Jobs */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Top Jobs by Applications</h2>
            <Link to="/jobs" className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100">
            {topJobs.length > 0 ? (
              topJobs.map((job, index) => (
                <div key={index} className="p-4 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-primary-100 rounded-xl flex items-center justify-center">
                      <Briefcase className="w-5 h-5 text-primary-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-slate-900 truncate">{job.title}</div>
                      <div className="text-sm text-slate-500">{job.department || 'General'} • {job.location || 'Remote'}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold text-slate-900">{job.applications_count}</div>
                      <div className="text-xs text-slate-500">applicants</div>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-slate-500">
                <Briefcase className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                <p>No active jobs</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* AI Insights Banner */}
      <div className="card bg-gradient-to-r from-primary-600 via-primary-700 to-purple-700 border-0 text-white overflow-hidden relative">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PHBhdGggZD0iTTM2IDM0djItSDI0di0yaDEyek0zNiAzMHYySDI0di0yaDEyek0zNiAyNnYySDI0di0yaDEyeiIvPjwvZz48L2c+PC9zdmc+')] opacity-50"></div>
        <div className="card-body relative z-10 flex items-center gap-6">
          <div className="w-16 h-16 bg-white/10 backdrop-blur-sm rounded-2xl flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-semibold mb-1">AI-Powered Insights</h3>
            <p className="text-white/80">Get intelligent recommendations to improve your hiring process and find the best candidates faster.</p>
          </div>
          <button className="btn bg-white text-primary-700 hover:bg-white/90 shadow-lg">
            <Zap className="w-4 h-4" />
            Explore Insights
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
