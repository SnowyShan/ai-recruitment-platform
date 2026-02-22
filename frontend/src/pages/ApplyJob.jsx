import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { publicAPI } from '../services/api';
import { MapPin, Briefcase, DollarSign, Sparkles, CheckCircle, ArrowLeft, Upload } from 'lucide-react';

const formatSalary = (min, max) => {
  if (!min && !max) return null;
  const fmt = (n) => `$${(n / 1000).toFixed(0)}k`;
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (min) return `From ${fmt(min)}`;
  return `Up to ${fmt(max)}`;
};

const ApplyJob = () => {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [resumeFile, setResumeFile] = useState(null);
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    cover_letter: '',
  });

  useEffect(() => {
    const fetchJob = async () => {
      try {
        const res = await publicAPI.getJob(id);
        setJob(res.data);
      } catch {
        setError('Job not found or no longer accepting applications.');
      } finally {
        setLoading(false);
      }
    };
    fetchJob();
  }, [id]);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) setResumeFile(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('job_id', id);
      formData.append('full_name', form.full_name);
      formData.append('email', form.email);
      if (form.phone) formData.append('phone', form.phone);
      if (form.cover_letter) formData.append('cover_letter', form.cover_letter);
      if (resumeFile) formData.append('resume', resumeFile);

      await publicAPI.apply(formData);
      setSubmitted(true);
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary-600/30 border-t-primary-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-slate-600">{error}</p>
          <Link to="/browse-jobs" className="btn btn-primary">Browse all jobs</Link>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="card p-10 max-w-md w-full text-center space-y-4">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle className="w-9 h-9 text-green-600" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Application Submitted!</h2>
          <p className="text-slate-600">
            Thanks, <strong>{form.full_name}</strong>! We've received your application for{' '}
            <strong>{job?.title}</strong>. We'll be in touch soon.
          </p>
          <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/browse-jobs" className="btn btn-secondary">Browse more jobs</Link>
            <Link to="/my-applications" className="btn btn-primary">Check my status</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Minimal header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <Link to="/browse-jobs" className="flex items-center gap-1 text-slate-500 hover:text-slate-700 text-sm">
            <ArrowLeft className="w-4 h-4" />
            Back to jobs
          </Link>
          <span className="text-slate-300">|</span>
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-primary-600 rounded-lg flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-slate-900 text-sm">TalentBridge AI</span>
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-10 space-y-8">
        {/* Job details */}
        <div className="card p-8 space-y-4">
          <h1 className="text-2xl font-bold text-slate-900">{job.title}</h1>
          <div className="flex flex-wrap gap-4 text-sm text-slate-500">
            {job.department && (
              <span className="flex items-center gap-1"><Briefcase className="w-4 h-4" />{job.department}</span>
            )}
            {job.location && (
              <span className="flex items-center gap-1"><MapPin className="w-4 h-4" />{job.location}</span>
            )}
            {formatSalary(job.salary_min, job.salary_max) && (
              <span className="flex items-center gap-1"><DollarSign className="w-4 h-4" />{formatSalary(job.salary_min, job.salary_max)}</span>
            )}
          </div>

          {job.description && (
            <div>
              <h3 className="font-semibold text-slate-700 mb-1">About this role</h3>
              <p className="text-slate-600 whitespace-pre-line text-sm leading-relaxed">{job.description}</p>
            </div>
          )}
          {job.responsibilities && (
            <div>
              <h3 className="font-semibold text-slate-700 mb-1">Responsibilities</h3>
              <p className="text-slate-600 whitespace-pre-line text-sm leading-relaxed">{job.responsibilities}</p>
            </div>
          )}
          {job.requirements && (
            <div>
              <h3 className="font-semibold text-slate-700 mb-1">Requirements</h3>
              <p className="text-slate-600 whitespace-pre-line text-sm leading-relaxed">{job.requirements}</p>
            </div>
          )}
          {job.benefits && (
            <div>
              <h3 className="font-semibold text-slate-700 mb-1">Benefits</h3>
              <p className="text-slate-600 whitespace-pre-line text-sm leading-relaxed">{job.benefits}</p>
            </div>
          )}
        </div>

        {/* Apply form */}
        <div className="card p-8">
          <h2 className="text-xl font-semibold text-slate-900 mb-6">Apply for this position</h2>

          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="label">Full Name <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  name="full_name"
                  value={form.full_name}
                  onChange={handleChange}
                  className="input w-full"
                  placeholder="Jane Smith"
                  required
                />
              </div>
              <div>
                <label className="label">Email Address <span className="text-red-500">*</span></label>
                <input
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  className="input w-full"
                  placeholder="jane@example.com"
                  required
                />
              </div>
            </div>

            <div>
              <label className="label">Phone Number <span className="text-slate-400 font-normal">(optional)</span></label>
              <input
                type="tel"
                name="phone"
                value={form.phone}
                onChange={handleChange}
                className="input w-full"
                placeholder="+1 555 000 0000"
              />
            </div>

            <div>
              <label className="label">Cover Letter <span className="text-slate-400 font-normal">(optional)</span></label>
              <textarea
                name="cover_letter"
                value={form.cover_letter}
                onChange={handleChange}
                className="input w-full h-32 resize-none"
                placeholder="Tell us why you're a great fit…"
              />
            </div>

            <div>
              <label className="label">Resume / CV <span className="text-slate-400 font-normal">(optional, PDF or Word)</span></label>
              <label className="flex flex-col items-center justify-center w-full border-2 border-dashed border-slate-200 rounded-xl p-6 cursor-pointer hover:border-primary-400 hover:bg-primary-50 transition-colors">
                <Upload className="w-8 h-8 text-slate-400 mb-2" />
                {resumeFile ? (
                  <span className="text-sm text-primary-600 font-medium">{resumeFile.name}</span>
                ) : (
                  <span className="text-sm text-slate-500">Click to upload or drag and drop</span>
                )}
                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="btn btn-primary w-full py-3 text-base"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Submitting…
                </span>
              ) : (
                'Submit Application'
              )}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default ApplyJob;
