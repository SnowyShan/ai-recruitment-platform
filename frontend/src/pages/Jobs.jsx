import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { jobsAPI } from '../services/api';
import {
  Briefcase,
  Plus,
  Search,
  Filter,
  MoreVertical,
  MapPin,
  Users,
  DollarSign,
  Eye,
  PlayCircle,
  PauseCircle,
  X,
} from 'lucide-react';

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
                    <button onClick={() => handlePublish(job.id)} className="btn btn-primary flex-1 py-2">
                      <PlayCircle className="w-4 h-4" />
                      Publish
                    </button>
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
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = { ...formData, salary_min: formData.salary_min ? parseInt(formData.salary_min) : null, salary_max: formData.salary_max ? parseInt(formData.salary_max) : null };
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
              <input type="text" name="title" value={formData.title} onChange={handleChange} className="input" placeholder="e.g., Senior Software Engineer" required />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Department</label>
                <input type="text" name="department" value={formData.department} onChange={handleChange} className="input" placeholder="e.g., Engineering" />
              </div>
              <div>
                <label className="label">Location</label>
                <input type="text" name="location" value={formData.location} onChange={handleChange} className="input" placeholder="e.g., San Francisco, CA" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
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
            <div className="grid grid-cols-2 gap-4">
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
          </div>
          <div className="flex items-center gap-3 mt-6 pt-6 border-t border-slate-100">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn btn-primary flex-1">{loading ? 'Creating...' : 'Create Job'}</button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Jobs;
