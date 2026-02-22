import { useState, useEffect } from 'react';
import { applicationsAPI, jobsAPI } from '../services/api';
import { FileText, Search, Filter, CheckCircle, XCircle, Clock, Eye, Sparkles, MessageSquare, X, Plus } from 'lucide-react';

const Applications = () => {
  const [applications, setApplications] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => { loadData(); }, [selectedJob, statusFilter]);

  const loadData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (selectedJob) params.job_id = selectedJob;
      if (statusFilter) params.status = statusFilter;
      
      const [appsRes, jobsRes] = await Promise.all([applicationsAPI.getAll(params), jobsAPI.getAll({ status: 'active' })]);
      setApplications(appsRes.data);
      setJobs(jobsRes.data);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleShortlist = async (id) => {
    try { await applicationsAPI.shortlist(id); loadData(); } catch (e) { console.error(e); }
  };

  const handleReject = async (id) => {
    try { await applicationsAPI.reject(id); loadData(); } catch (e) { console.error(e); }
  };

  const getStatusBadge = (status) => {
    const styles = { pending: 'badge-warning', screening: 'badge-info', shortlisted: 'badge-primary', interview: 'badge-info', offered: 'badge-success', hired: 'badge-success', rejected: 'badge-danger' };
    return styles[status] || 'badge-secondary';
  };

  const getScoreColor = (score) => { if (score >= 80) return 'score-high'; if (score >= 60) return 'score-medium'; return 'score-low'; };

  const getRecommendationBadge = (rec) => {
    const styles = { strong_yes: 'bg-emerald-100 text-emerald-700', yes: 'bg-green-100 text-green-700', maybe: 'bg-amber-100 text-amber-700', no: 'bg-red-100 text-red-700' };
    return styles[rec] || 'bg-slate-100 text-slate-600';
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Applications</h1>
          <p className="text-slate-500 mt-1">Review and manage job applications</p>
        </div>
        <button onClick={() => setShowCreateModal(true)} className="btn btn-primary"><Plus className="w-4 h-4" /> New Application</button>
      </div>

      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <select value={selectedJob} onChange={(e) => setSelectedJob(e.target.value)} className="input py-2 w-auto min-w-[200px]">
            <option value="">All Jobs</option>
            {jobs.map(job => <option key={job.id} value={job.id}>{job.title}</option>)}
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input py-2 w-auto min-w-[150px]">
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="screening">Screening</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="interview">Interview</option>
            <option value="offered">Offered</option>
            <option value="hired">Hired</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64"><div className="spinner"></div></div>
      ) : applications.length > 0 ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="table-header">Candidate</th>
                  <th className="table-header">Job</th>
                  <th className="table-header">Resume Match</th>
                  <th className="table-header">AI Recommendation</th>
                  <th className="table-header">Status</th>
                  <th className="table-header">Applied</th>
                  <th className="table-header">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {applications.map((app) => (
                  <tr key={app.id} className="hover:bg-slate-50 transition-colors">
                    <td className="table-cell">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-slate-200 to-slate-300 rounded-full flex items-center justify-center font-medium text-slate-600">
                          {app.candidate?.full_name?.charAt(0)?.toUpperCase() || '?'}
                        </div>
                        <div>
                          <div className="font-medium text-slate-900">{app.candidate?.full_name}</div>
                          <div className="text-sm text-slate-500">{app.candidate?.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="table-cell">
                      <div className="font-medium text-slate-900">{app.job?.title}</div>
                      <div className="text-sm text-slate-500">{app.job?.department}</div>
                    </td>
                    <td className="table-cell">
                      {app.match_score != null
                        ? <div className={`score-badge ${getScoreColor(app.match_score)}`}>{Math.round(app.match_score)}%</div>
                        : <span className="text-xs text-slate-400">No resume</span>
                      }
                    </td>
                    <td className="table-cell">
                      {app.ai_recommendation && (
                        <span className={`badge ${getRecommendationBadge(app.ai_recommendation)}`}>
                          {app.ai_recommendation.replace('_', ' ')}
                        </span>
                      )}
                    </td>
                    <td className="table-cell">
                      <span className={`badge ${getStatusBadge(app.status)}`}>{app.status}</span>
                    </td>
                    <td className="table-cell text-slate-500">
                      {new Date(app.applied_at).toLocaleDateString()}
                    </td>
                    <td className="table-cell">
                      <div className="flex items-center gap-2">
                        <button className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700" title="View"><Eye className="w-4 h-4" /></button>
                        {app.status === 'pending' && (
                          <>
                            <button onClick={() => handleShortlist(app.id)} className="p-2 rounded-lg hover:bg-emerald-100 text-emerald-600" title="Shortlist"><CheckCircle className="w-4 h-4" /></button>
                            <button onClick={() => handleReject(app.id)} className="p-2 rounded-lg hover:bg-red-100 text-red-600" title="Reject"><XCircle className="w-4 h-4" /></button>
                          </>
                        )}
                        {app.status === 'shortlisted' && (
                          <button className="p-2 rounded-lg hover:bg-purple-100 text-purple-600" title="Start AI Screening"><Sparkles className="w-4 h-4" /></button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card p-12 text-center">
          <FileText className="w-16 h-16 mx-auto mb-4 text-slate-300" />
          <h3 className="text-xl font-semibold text-slate-900 mb-2">No applications found</h3>
          <p className="text-slate-500">Applications will appear here when candidates apply to your jobs</p>
        </div>
      )}

      {showCreateModal && <CreateApplicationModal jobs={jobs} onClose={() => setShowCreateModal(false)} onSuccess={() => { setShowCreateModal(false); loadData(); }} />}
    </div>
  );
};

const CreateApplicationModal = ({ jobs, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({ job_id: '', email: '', full_name: '', phone: '', cover_letter: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await applicationsAPI.create({ ...formData, job_id: parseInt(formData.job_id) });
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create application');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden animate-in">
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900">New Application</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {error && <div className="mb-4 p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">{error}</div>}
          <div className="space-y-5">
            <div>
              <label className="label">Select Job *</label>
              <select name="job_id" value={formData.job_id} onChange={handleChange} className="input" required>
                <option value="">Choose a job...</option>
                {jobs.map(job => <option key={job.id} value={job.id}>{job.title}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Candidate Name *</label>
              <input type="text" name="full_name" value={formData.full_name} onChange={handleChange} className="input" required />
            </div>
            <div>
              <label className="label">Email *</label>
              <input type="email" name="email" value={formData.email} onChange={handleChange} className="input" required />
            </div>
            <div>
              <label className="label">Phone</label>
              <input type="tel" name="phone" value={formData.phone} onChange={handleChange} className="input" />
            </div>
            <div>
              <label className="label">Cover Letter</label>
              <textarea name="cover_letter" value={formData.cover_letter} onChange={handleChange} className="input min-h-[100px]" />
            </div>
          </div>
          <div className="flex items-center gap-3 mt-6 pt-6 border-t border-slate-100">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn btn-primary flex-1">{loading ? 'Creating...' : 'Create Application'}</button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Applications;
