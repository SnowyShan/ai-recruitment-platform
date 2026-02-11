import { useState, useEffect } from 'react';
import { screeningsAPI, applicationsAPI } from '../services/api';
import { MessageSquare, Plus, Search, PlayCircle, CheckCircle, XCircle, Clock, Eye, Sparkles, X, Calendar } from 'lucide-react';

const Screenings = () => {
  const [screenings, setScreenings] = useState([]);
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => { loadData(); }, [statusFilter]);

  const loadData = async () => {
    try {
      setLoading(true);
      const params = statusFilter ? { status: statusFilter } : {};
      const [screenRes, appsRes] = await Promise.all([
        screeningsAPI.getAll(params),
        applicationsAPI.getAll({ status: 'shortlisted' })
      ]);
      setScreenings(screenRes.data);
      setApplications(appsRes.data);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async (id) => {
    try { await screeningsAPI.start(id); loadData(); } catch (e) { console.error(e); }
  };

  const handleComplete = async (id) => {
    try { await screeningsAPI.complete(id); loadData(); } catch (e) { console.error(e); }
  };

  const handleCancel = async (id) => {
    try { await screeningsAPI.cancel(id); loadData(); } catch (e) { console.error(e); }
  };

  const getStatusBadge = (status) => {
    const styles = { scheduled: 'bg-blue-100 text-blue-700', in_progress: 'bg-amber-100 text-amber-700', completed: 'bg-emerald-100 text-emerald-700', cancelled: 'bg-red-100 text-red-700' };
    return styles[status] || 'bg-slate-100 text-slate-600';
  };

  const getScoreColor = (score) => { if (score >= 80) return 'text-emerald-600 bg-emerald-50'; if (score >= 60) return 'text-amber-600 bg-amber-50'; return 'text-red-600 bg-red-50'; };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">AI Screenings</h1>
          <p className="text-slate-500 mt-1">Automated candidate screening interviews</p>
        </div>
        <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
          <Plus className="w-4 h-4" /> Schedule Screening
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Scheduled', value: screenings.filter(s => s.status === 'scheduled').length, color: 'bg-blue-500' },
          { label: 'In Progress', value: screenings.filter(s => s.status === 'in_progress').length, color: 'bg-amber-500' },
          { label: 'Completed', value: screenings.filter(s => s.status === 'completed').length, color: 'bg-emerald-500' },
          { label: 'Cancelled', value: screenings.filter(s => s.status === 'cancelled').length, color: 'bg-red-500' },
        ].map((stat, i) => (
          <div key={i} className="card p-4">
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${stat.color}`}></div>
              <span className="text-slate-500">{stat.label}</span>
            </div>
            <div className="text-2xl font-bold text-slate-900 mt-2">{stat.value}</div>
          </div>
        ))}
      </div>

      <div className="card p-4">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input py-2 w-auto min-w-[150px]">
          <option value="">All Status</option>
          <option value="scheduled">Scheduled</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64"><div className="spinner"></div></div>
      ) : screenings.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {screenings.map((screening) => (
            <div key={screening.id} className="card hover:shadow-lg transition-all">
              <div className="card-body">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                      <Sparkles className="w-6 h-6 text-purple-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-900">Screening #{screening.id}</h3>
                      <p className="text-sm text-slate-500">Application #{screening.application_id}</p>
                    </div>
                  </div>
                  <span className={`badge ${getStatusBadge(screening.status)}`}>{screening.status.replace('_', ' ')}</span>
                </div>

                {screening.status === 'completed' && screening.overall_score && (
                  <div className="grid grid-cols-4 gap-3 mb-4">
                    {[
                      { label: 'Technical', score: screening.technical_score },
                      { label: 'Communication', score: screening.communication_score },
                      { label: 'Cultural Fit', score: screening.cultural_fit_score },
                      { label: 'Overall', score: screening.overall_score },
                    ].map((item, i) => (
                      <div key={i} className="text-center">
                        <div className={`text-lg font-bold px-2 py-1 rounded ${getScoreColor(item.score)}`}>
                          {item.score ? Math.round(item.score) : '-'}
                        </div>
                        <div className="text-xs text-slate-500 mt-1">{item.label}</div>
                      </div>
                    ))}
                  </div>
                )}

                {screening.recommendation && (
                  <div className="mb-4 p-3 bg-slate-50 rounded-lg">
                    <span className="text-sm text-slate-500">Recommendation: </span>
                    <span className="font-medium text-slate-900">{screening.recommendation.replace('_', ' ')}</span>
                  </div>
                )}

                <div className="flex items-center gap-2 pt-4 border-t border-slate-100">
                  {screening.status === 'scheduled' && (
                    <>
                      <button onClick={() => handleStart(screening.id)} className="btn btn-primary flex-1 py-2">
                        <PlayCircle className="w-4 h-4" /> Start
                      </button>
                      <button onClick={() => handleCancel(screening.id)} className="btn btn-secondary py-2">
                        <XCircle className="w-4 h-4" />
                      </button>
                    </>
                  )}
                  {screening.status === 'in_progress' && (
                    <button onClick={() => handleComplete(screening.id)} className="btn btn-success flex-1 py-2">
                      <CheckCircle className="w-4 h-4" /> Complete
                    </button>
                  )}
                  {screening.status === 'completed' && (
                    <button className="btn btn-secondary flex-1 py-2">
                      <Eye className="w-4 h-4" /> View Report
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card p-12 text-center">
          <MessageSquare className="w-16 h-16 mx-auto mb-4 text-slate-300" />
          <h3 className="text-xl font-semibold text-slate-900 mb-2">No screenings found</h3>
          <p className="text-slate-500 mb-6">Schedule AI-powered screening interviews for shortlisted candidates</p>
          <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
            <Plus className="w-4 h-4" /> Schedule Screening
          </button>
        </div>
      )}

      {showCreateModal && <CreateScreeningModal applications={applications} onClose={() => setShowCreateModal(false)} onSuccess={() => { setShowCreateModal(false); loadData(); }} />}
    </div>
  );
};

const CreateScreeningModal = ({ applications, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({ application_id: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await screeningsAPI.create({ application_id: parseInt(formData.application_id) });
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to schedule screening');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden animate-in">
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900">Schedule AI Screening</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6">
          {error && <div className="mb-4 p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">{error}</div>}
          
          <div className="mb-6">
            <label className="label">Select Shortlisted Application *</label>
            <select value={formData.application_id} onChange={(e) => setFormData({ application_id: e.target.value })} className="input" required>
              <option value="">Choose an application...</option>
              {applications.map(app => (
                <option key={app.id} value={app.id}>
                  {app.candidate?.full_name} - {app.job?.title}
                </option>
              ))}
            </select>
            {applications.length === 0 && (
              <p className="text-sm text-amber-600 mt-2">No shortlisted applications available. Shortlist candidates first.</p>
            )}
          </div>

          <div className="p-4 bg-purple-50 rounded-xl mb-6">
            <div className="flex items-center gap-3 mb-2">
              <Sparkles className="w-5 h-5 text-purple-600" />
              <span className="font-medium text-purple-900">AI-Powered Screening</span>
            </div>
            <p className="text-sm text-purple-700">
              Our AI will conduct an automated screening interview, evaluating technical skills, communication, and cultural fit.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={loading || !formData.application_id} className="btn btn-primary flex-1">
              {loading ? 'Scheduling...' : 'Schedule Screening'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Screenings;
