import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { publicAPI } from '../services/api';
import { Search, MapPin, Briefcase, DollarSign, ChevronRight, Sparkles } from 'lucide-react';

const JOB_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'full_time', label: 'Full-time' },
  { value: 'part_time', label: 'Part-time' },
  { value: 'contract', label: 'Contract' },
  { value: 'internship', label: 'Internship' },
];

const formatSalary = (min, max) => {
  if (!min && !max) return null;
  const fmt = (n) => `$${(n / 1000).toFixed(0)}k`;
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (min) return `From ${fmt(min)}`;
  return `Up to ${fmt(max)}`;
};

const jobTypeBadge = (type) => {
  const map = {
    full_time: 'bg-green-100 text-green-700',
    part_time: 'bg-blue-100 text-blue-700',
    contract: 'bg-purple-100 text-purple-700',
    internship: 'bg-orange-100 text-orange-700',
  };
  const label = type?.replace('_', ' ') ?? type;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${map[type] ?? 'bg-slate-100 text-slate-600'}`}>
      {label}
    </span>
  );
};

const BrowseJobs = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [jobType, setJobType] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const fetchJobs = async (s, t) => {
    setLoading(true);
    try {
      const params = { skip: 0, limit: 50 };
      if (s) params.search = s;
      if (t) params.job_type = t;
      const res = await publicAPI.getJobs(params);
      setJobs(res.data);
    } catch (err) {
      console.error('Failed to load jobs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs(search, jobType);
  }, [search, jobType]);

  const handleSearch = (e) => {
    e.preventDefault();
    setSearch(searchInput);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Minimal header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-slate-900">TalentBridge AI</span>
          </Link>
          <Link to="/my-applications" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
            Check my application status →
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-10">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Open Positions</h1>
          <p className="text-slate-500">Find your next opportunity and apply in minutes</p>
        </div>

        {/* Search + filter bar */}
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3 mb-8">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by title, department, or location…"
              className="input pl-10 w-full"
            />
          </div>
          <select
            value={jobType}
            onChange={(e) => setJobType(e.target.value)}
            className="input w-full sm:w-48"
          >
            {JOB_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <button type="submit" className="btn btn-primary px-6">
            Search
          </button>
        </form>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 border-2 border-primary-600/30 border-t-primary-600 rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            No open positions match your search. Try different keywords.
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-slate-500">{jobs.length} position{jobs.length !== 1 ? 's' : ''} found</p>
            {jobs.map((job) => (
              <div key={job.id} className="card p-6 hover:shadow-md transition-shadow">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                  <div className="space-y-2 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-semibold text-slate-900">{job.title}</h2>
                      {jobTypeBadge(job.job_type)}
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm text-slate-500">
                      {job.department && (
                        <span className="flex items-center gap-1">
                          <Briefcase className="w-4 h-4" />
                          {job.department}
                        </span>
                      )}
                      {job.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-4 h-4" />
                          {job.location}
                        </span>
                      )}
                      {formatSalary(job.salary_min, job.salary_max) && (
                        <span className="flex items-center gap-1">
                          <DollarSign className="w-4 h-4" />
                          {formatSalary(job.salary_min, job.salary_max)}
                        </span>
                      )}
                    </div>
                    {job.description && (
                      <p className="text-sm text-slate-600 line-clamp-2">{job.description}</p>
                    )}
                  </div>
                  <Link
                    to={`/browse-jobs/${job.id}`}
                    className="btn btn-primary shrink-0 flex items-center gap-1"
                  >
                    View & Apply
                    <ChevronRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default BrowseJobs;
