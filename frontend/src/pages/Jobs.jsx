import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { jobsAPI } from '../services/api';
import axios from 'axios';
import {
  Briefcase,
  Plus,
  Search,
  MapPin,
  Users,
  DollarSign,
  Eye,
  PlayCircle,
  PauseCircle,
  X,
  ChevronDown,
  ChevronUp,
  CheckSquare,
  Square,
  Layers,
  Loader2,
} from 'lucide-react';

const INTERVIEW_API = import.meta.env.VITE_INTERVIEW_API_URL || 'http://localhost:8001';

const Jobs = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadJobs();
  }, [statusFilter]);

  const loadJobs = async () => {
    try {
      setLoading(true);
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (searchTerm) params.search = searchTerm;
      
      const response = await jobsAPI.getAll(params);
      setJobs(response.data);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    loadJobs();
  };

  const handlePublish = async (jobId) => {
    try {
      await jobsAPI.publish(jobId);
      loadJobs();
    } catch (error) {
      console.error('Failed to publish job:', error);
    }
  };

  const handleClose = async (jobId) => {
    try {
      await jobsAPI.close(jobId);
      loadJobs();
    } catch (error) {
      console.error('Failed to close job:', error);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      draft: 'bg-slate-100 text-slate-600',
      active: 'bg-emerald-100 text-emerald-700',
      paused: 'bg-amber-100 text-amber-700',
      closed: 'bg-red-100 text-red-700',
    };
    return styles[status] || 'bg-slate-100 text-slate-600';
  };

  const formatSalary = (min, max) => {
    if (!min && !max) return 'Not specified';
    if (min && max) return `$${(min/1000).toFixed(0)}K - $${(max/1000).toFixed(0)}K`;
    if (min) return `From $${(min/1000).toFixed(0)}K`;
    return `Up to $${(max/1000).toFixed(0)}K`;
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Jobs</h1>
          <p className="text-slate-500 mt-1">Manage your job postings</p>
        </div>
        <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
          <Plus className="w-4 h-4" />
          Create Job
        </button>
      </div>

      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <form onSubmit={handleSearch} className="flex-1">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search jobs..."
                className="input pl-12"
              />
            </div>
          </form>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input py-2 w-auto min-w-[150px]"
          >
            <option value="">All Status</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="spinner"></div>
        </div>
      ) : jobs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {jobs.map((job) => (
            <div key={job.id} className="card hover:shadow-lg transition-all group">
              <div className="card-body">
                <div className="flex items-start justify-between mb-4">
                  <div className="w-12 h-12 bg-primary-100 rounded-xl flex items-center justify-center">
                    <Briefcase className="w-6 h-6 text-primary-600" />
                  </div>
                  <span className={`badge ${getStatusBadge(job.status)}`}>{job.status}</span>
                </div>

                <h3 className="text-lg font-semibold text-slate-900 mb-2 group-hover:text-primary-600 transition-colors">
                  {job.title}
                </h3>
                
                <div className="space-y-2 mb-4">
                  {job.department && (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Briefcase className="w-4 h-4" />
                      {job.department}
                    </div>
                  )}
                  {job.location && (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <MapPin className="w-4 h-4" />
                      {job.location}
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <DollarSign className="w-4 h-4" />
                    {formatSalary(job.salary_min, job.salary_max)}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Users className="w-4 h-4" />
                    {job.applications_count || 0} applicants
                  </div>
                </div>

                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-100">
                  <Link to={`/jobs/${job.id}`} className="btn btn-secondary flex-1 py-2">
                    <Eye className="w-4 h-4" />
                    View
                  </Link>
                  {job.status === 'draft' && (
                    (job.setup_status === 'generating' || job.setup_status === null) ? (
                      <div className="flex-1 flex items-center gap-1.5 justify-center py-2 px-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm font-medium cursor-not-allowed">
                        <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                        <span className="truncate">Generating…</span>
                      </div>
                    ) : (
                      <button onClick={() => handlePublish(job.id)} className="btn btn-primary flex-1 py-2">
                        <PlayCircle className="w-4 h-4" />
                        Publish
                      </button>
                    )
                  )}
                  {job.status === 'active' && (
                    <button onClick={() => handleClose(job.id)} className="btn btn-secondary flex-1 py-2">
                      <PauseCircle className="w-4 h-4" />
                      Close
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card p-12 text-center">
          <Briefcase className="w-16 h-16 mx-auto mb-4 text-slate-300" />
          <h3 className="text-xl font-semibold text-slate-900 mb-2">No jobs found</h3>
          <p className="text-slate-500 mb-6">Create your first job posting to start receiving applications</p>
          <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
            <Plus className="w-4 h-4" />
            Create Job
          </button>
        </div>
      )}

      {showCreateModal && (
        <CreateJobModal onClose={() => setShowCreateModal(false)} onSuccess={() => { setShowCreateModal(false); loadJobs(); }} />
      )}
    </div>
  );
};

const CreateJobModal = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    title: '', department: '', location: '', job_type: 'full_time', experience_level: 'mid',
    salary_min: '', salary_max: '', description: '', requirements: '', skills_required: '',
    interview_behavioral_pct: 20,
    verify_coding_ability: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Question bank
  const [bankOpen, setBankOpen] = useState(false);
  const [bankQuestions, setBankQuestions] = useState([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [selectedQIds, setSelectedQIds] = useState([]);
  const titleDebounceRef = useRef(null);

  // Load question bank on modal open (domain=general to show all available questions)
  useEffect(() => {
    loadBankQuestions('general');
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));

    // When title changes, debounce a question bank fetch
    if (name === 'title') {
      clearTimeout(titleDebounceRef.current);
      titleDebounceRef.current = setTimeout(() => loadBankQuestions(value), 600);
    }
  };

  const loadBankQuestions = async (title) => {
    if (!title || title.length < 3) { setBankQuestions([]); return; }
    setBankLoading(true);
    try {
      const res = await axios.get(`${INTERVIEW_API}/api/interview/question-bank`, {
        params: { domain: inferDomainFE(title), limit: 20 },
      });
      setBankQuestions(res.data.questions || []);
    } catch (_) {
      setBankQuestions([]);
    } finally {
      setBankLoading(false);
    }
  };

  // Simple client-side domain inference (mirrors backend logic)
  const inferDomainFE = (title) => {
    const t = title.toLowerCase();
    if (/ios|swift|xcode|uikit|swiftui/.test(t)) return 'ios';
    if (/android|kotlin/.test(t)) return 'android';
    if (/frontend|front-end|react|vue|angular/.test(t)) return 'frontend';
    if (/data sci|machine learn|ml engineer|ai engineer|data engineer/.test(t)) return 'data';
    if (/devops|sre|kubernetes|docker|cloud|platform/.test(t)) return 'devops';
    if (/mobile|react native|flutter/.test(t)) return 'mobile';
    if (/full.?stack/.test(t)) return 'fullstack';
    if (/backend|back-end|python|django|fastapi|golang|node/.test(t)) return 'backend';
    return 'general';
  };

  const toggleQuestion = (id) => {
    setSelectedQIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const numTechnical = Math.max(1, Math.round(8 * (1 - formData.interview_behavioral_pct / 100)));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = {
        ...formData,
        salary_min: formData.salary_min ? parseInt(formData.salary_min) : null,
        salary_max: formData.salary_max ? parseInt(formData.salary_max) : null,
        interview_behavioral_pct: parseInt(formData.interview_behavioral_pct) || 20,
        verify_coding_ability: !!formData.verify_coding_ability,
        selected_question_ids: selectedQIds,
      };
      await jobsAPI.create(data);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create job');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden animate-in">
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900">Create New Job</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {error && <div className="mb-4 p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">{error}</div>}
          <div className="space-y-5">
            <div>
              <label className="label">Job Title *</label>
              <input type="text" name="title" value={formData.title} onChange={handleChange} className="input" placeholder="e.g., Senior iOS Engineer" required />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Department</label>
                <input type="text" name="department" value={formData.department} onChange={handleChange} className="input" placeholder="e.g., Engineering" />
              </div>
              <div>
                <label className="label">Location</label>
                <input type="text" name="location" value={formData.location} onChange={handleChange} className="input" placeholder="e.g., San Francisco, CA" />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Job Type</label>
                <select name="job_type" value={formData.job_type} onChange={handleChange} className="input">
                  <option value="full_time">Full Time</option>
                  <option value="part_time">Part Time</option>
                  <option value="contract">Contract</option>
                  <option value="internship">Internship</option>
                </select>
              </div>
              <div>
                <label className="label">Experience Level</label>
                <select name="experience_level" value={formData.experience_level} onChange={handleChange} className="input">
                  <option value="entry">Entry Level</option>
                  <option value="mid">Mid Level</option>
                  <option value="senior">Senior Level</option>
                  <option value="lead">Lead</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Salary Min ($)</label>
                <input type="number" name="salary_min" value={formData.salary_min} onChange={handleChange} className="input" placeholder="e.g., 80000" />
              </div>
              <div>
                <label className="label">Salary Max ($)</label>
                <input type="number" name="salary_max" value={formData.salary_max} onChange={handleChange} className="input" placeholder="e.g., 120000" />
              </div>
            </div>
            <div>
              <label className="label">Job Description *</label>
              <textarea name="description" value={formData.description} onChange={handleChange} className="input min-h-[120px]" placeholder="Describe the role..." required />
            </div>
            <div>
              <label className="label">Requirements</label>
              <textarea name="requirements" value={formData.requirements} onChange={handleChange} className="input min-h-[80px]" placeholder="List required qualifications..." />
            </div>
            <div>
              <label className="label">Skills Required</label>
              <input type="text" name="skills_required" value={formData.skills_required} onChange={handleChange} className="input" placeholder="e.g., Python, React, AWS" />
            </div>

            {/* ── Interview Setup ── */}
            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <div className="bg-slate-50 px-4 py-3 flex items-center gap-2">
                <Layers className="w-4 h-4 text-slate-500" />
                <span className="text-sm font-semibold text-slate-700">Interview Setup</span>
              </div>
              <div className="p-4 space-y-4">
                {/* Behavioral split */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="label mb-0">Behavioral Questions</label>
                    <span className="text-sm font-semibold text-slate-700">{formData.interview_behavioral_pct}%</span>
                  </div>
                  <input
                    type="range" name="interview_behavioral_pct"
                    min={0} max={50} step={5}
                    value={formData.interview_behavioral_pct}
                    onChange={handleChange}
                    className="w-full accent-primary-600"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    For 8 questions: <strong>{Math.max(1, Math.round(8 * formData.interview_behavioral_pct / 100))} behavioral</strong>, <strong>{8 - Math.max(1, Math.round(8 * formData.interview_behavioral_pct / 100))} technical</strong> — technical questions are pre-generated and reused across candidates.
                  </p>
                </div>

                {/* Verify coding ability */}
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.verify_coding_ability}
                    onChange={e => setFormData(prev => ({ ...prev, verify_coding_ability: e.target.checked }))}
                    className="mt-0.5 accent-primary-600"
                  />
                  <div>
                    <span className="text-sm font-medium text-slate-700">Verify coding ability</span>
                    <p className="text-xs text-slate-500 mt-0.5">Adds a logic-based coding question to the interview. Candidate can type their solution.</p>
                  </div>
                </label>

                {/* Question bank selector */}
                {(bankQuestions.length > 0 || bankLoading) && (
                  <div>
                    <button
                      type="button"
                      onClick={() => setBankOpen(v => !v)}
                      className="w-full flex items-center justify-between text-sm font-medium text-primary-600 hover:text-primary-700"
                    >
                      <span>
                        {bankLoading && bankQuestions.length === 0
                          ? 'Loading question bank…'
                          : `Reuse from question bank (${bankQuestions.length} available)`}
                        {selectedQIds.length > 0 && ` · ${selectedQIds.length}/${numTechnical} selected`}
                      </span>
                      {bankOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    {bankOpen && (
                      <div className="mt-2 border border-slate-200 rounded-lg overflow-hidden max-h-48 overflow-y-auto">
                        {bankLoading ? (
                          <div className="p-4 text-sm text-slate-400 text-center">Loading…</div>
                        ) : (
                          bankQuestions.map(q => (
                            <button
                              key={q.id}
                              type="button"
                              onClick={() => toggleQuestion(q.id)}
                              className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-slate-50 border-b border-slate-100 last:border-0"
                            >
                              {selectedQIds.includes(q.id)
                                ? <CheckSquare className="w-4 h-4 text-primary-600 flex-shrink-0 mt-0.5" />
                                : <Square className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
                              }
                              <div className="flex-1 min-w-0">
                                <p className="text-xs text-slate-700 leading-snug line-clamp-2">{q.question}</p>
                                <p className="text-xs text-slate-400 mt-0.5">{q.topic} · difficulty {q.difficulty}</p>
                              </div>
                              {q.audio_path && <span className="text-xs text-emerald-600 flex-shrink-0">🔊</span>}
                            </button>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 mt-6 pt-6 border-t border-slate-100">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn btn-primary flex-1">
              {loading ? 'Creating…' : 'Create Job'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Jobs;
