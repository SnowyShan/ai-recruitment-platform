import { useState } from 'react';
import { Link } from 'react-router-dom';
import { publicAPI } from '../services/api';
import { Sparkles, Search, Mail } from 'lucide-react';

const STATUS_STYLES = {
  pending:     'bg-slate-100 text-slate-600',
  screening:   'bg-blue-100 text-blue-700',
  shortlisted: 'bg-indigo-100 text-indigo-700',
  interview:   'bg-purple-100 text-purple-700',
  offered:     'bg-green-100 text-green-700',
  hired:       'bg-emerald-100 text-emerald-700',
  rejected:    'bg-red-100 text-red-600',
};

const StatusBadge = ({ status }) => (
  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_STYLES[status] ?? 'bg-slate-100 text-slate-600'}`}>
    {status}
  </span>
);

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

const CandidateStatus = () => {
  const [email, setEmail] = useState('');
  const [inputEmail, setInputEmail] = useState('');
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await publicAPI.getStatus(inputEmail);
      setApplications(res.data);
      setEmail(inputEmail);
      setSearched(true);
    } catch {
      setError('Failed to fetch applications. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Minimal header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-slate-900">TalentBridge AI</span>
          </Link>
          <Link to="/browse-jobs" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
            Browse openings →
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-10">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">My Applications</h1>
          <p className="text-slate-500">Enter the email you used when applying to see your application status.</p>
        </div>

        <form onSubmit={handleSubmit} className="flex gap-3 mb-8">
          <div className="relative flex-1">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="email"
              value={inputEmail}
              onChange={(e) => setInputEmail(e.target.value)}
              placeholder="you@example.com"
              className="input pl-10 w-full"
              required
            />
          </div>
          <button type="submit" disabled={loading} className="btn btn-primary flex items-center gap-2">
            <Search className="w-4 h-4" />
            {loading ? 'Checking…' : 'Check Status'}
          </button>
        </form>

        {error && (
          <div className="p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm mb-6">
            {error}
          </div>
        )}

        {searched && (
          applications.length === 0 ? (
            <div className="card p-10 text-center space-y-3">
              <p className="text-slate-600 font-medium">No applications found for <strong>{email}</strong>.</p>
              <p className="text-slate-500 text-sm">Make sure you're using the same email you applied with.</p>
              <Link to="/browse-jobs" className="btn btn-primary inline-flex mt-2">Browse open positions</Link>
            </div>
          ) : (
            <div className="card overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100">
                <p className="text-sm text-slate-500">
                  Showing {applications.length} application{applications.length !== 1 ? 's' : ''} for <strong>{email}</strong>
                </p>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                  <tr>
                    <th className="px-6 py-3 text-left">Position</th>
                    <th className="px-6 py-3 text-left">Status</th>
                    <th className="px-6 py-3 text-left">Applied</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {applications.map((app) => (
                    <tr key={app.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-900">{app.job_title}</div>
                        {app.job_department && (
                          <div className="text-xs text-slate-400">{app.job_department}</div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={app.status} />
                      </td>
                      <td className="px-6 py-4 text-slate-500">{formatDate(app.applied_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </main>
    </div>
  );
};

export default CandidateStatus;
