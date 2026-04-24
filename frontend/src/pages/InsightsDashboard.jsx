import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function InsightsDashboard() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`http://localhost:8000/api/jobs/${jobId}/insights`)
      .then(r => r.json())
      .then(data => { setInsights(data); setLoading(false); })
      .catch(err => {
        console.error('Failed to load insights:', err);
        setLoading(false);
      });
  }, [jobId]);

  const handleStatusChange = async (screeningId, status) => {
    try {
      await fetch(`http://localhost:8000/api/screenings/${screeningId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      });
      setInsights(prev => ({
        ...prev,
        candidates: prev.candidates.map(c =>
          c.screening_id === screeningId ? { ...c, recruiter_status: status } : c
        )
      }));
    } catch (err) {
      console.error('Failed to update status:', err);
      alert('Failed to update status. Please try again.');
    }
  };

  if (loading) return <div className="flex items-center justify-center h-screen bg-slate-50"><div className="spinner"></div></div>;

  if (!insights || insights.candidate_count === 0) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full text-center">
          <h1 className="text-2xl font-bold text-slate-900 mb-4">No Insights Available</h1>
          <p className="text-slate-600 mb-6">
            No completed interviews yet for this role. Insights will appear once candidates have completed their interviews.
          </p>
          <button onClick={() => navigate(-1)} className="btn btn-primary">
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const distData = Object.entries(insights.score_distribution).map(([range, count]) => ({ range, count }));

  return (
    <div className="min-h-screen bg-slate-50 p-4 sm:p-6 max-w-7xl mx-auto">
      <button onClick={() => navigate(-1)} className="btn btn-secondary mb-6">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-slate-900 mb-1">Hiring Insights</h1>
      <p className="text-slate-500 mb-6">
        {insights.candidate_count} candidates · Avg score: <strong className="text-slate-900">{insights.average_score}/100</strong>
      </p>

      {/* Claude cohort summary */}
      <section className="card mb-6 p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Cohort Analysis</h2>
        <p className="text-lg text-slate-800 mb-4">
          💡 {insights.cohort_summary?.hiring_recommendation || 'No recommendation available'}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-slate-900 mb-3">Common Strengths</h3>
            <ul className="space-y-2">
              {(insights.cohort_summary?.common_strengths || []).map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-slate-700">
                  <span className="text-green-500 mt-0.5">✓</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 mb-3">Common Gaps</h3>
            <ul className="space-y-2">
              {(insights.cohort_summary?.common_weaknesses || []).map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-slate-700">
                  <span className="text-amber-500 mt-0.5">!</span>
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Score distribution */}
      <section className="card mb-6 p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Score Distribution</h2>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={distData}>
            <XAxis dataKey="range" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#6366f1" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* Ranked candidate list */}
      <section className="card p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Candidates (ranked by score)</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px]">
            <thead>
              <tr className="text-left border-b border-slate-200">
                <th className="py-3 px-4 font-semibold text-slate-900">Name</th>
                <th className="py-3 px-4 font-semibold text-slate-900">Score</th>
                <th className="py-3 px-4 font-semibold text-slate-900">Recommendation</th>
                <th className="py-3 px-4 font-semibold text-slate-900">Status</th>
                <th className="py-3 px-4 font-semibold text-slate-900 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {insights.candidates.map((c) => (
                <tr key={c.screening_id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="py-3 px-4 font-medium text-slate-900">{c.candidate_name}</td>
                  <td className="py-3 px-4">
                    <span className={`inline-block px-2 py-1 rounded-full text-sm font-semibold ${
                      c.overall_score >= 80 ? 'bg-green-100 text-green-700' :
                      c.overall_score >= 60 ? 'bg-yellow-100 text-yellow-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {c.overall_score}/100
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-slate-600 max-w-xs truncate">
                    {c.recommendation || 'N/A'}
                  </td>
                  <td className="py-3 px-4">
                    {c.recruiter_status === 'advanced' && (
                      <span className="inline-block px-2 py-1 rounded-full text-sm font-semibold bg-green-100 text-green-700">
                        ✓ Advanced
                      </span>
                    )}
                    {c.recruiter_status === 'rejected' && (
                      <span className="inline-block px-2 py-1 rounded-full text-sm font-semibold bg-red-100 text-red-700">
                        ✗ Rejected
                      </span>
                    )}
                    {(!c.recruiter_status || c.recruiter_status === 'pending') && (
                      <span className="inline-block px-2 py-1 rounded-full text-sm font-semibold bg-gray-100 text-gray-700">
                        Pending
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => handleStatusChange(c.screening_id, 'advanced')}
                        className="text-xs px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-colors"
                      >
                        Advance
                      </button>
                      <button
                        onClick={() => handleStatusChange(c.screening_id, 'rejected')}
                        className="text-xs px-3 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
                      >
                        Reject
                      </button>
                      <button
                        onClick={() => navigate(`/screenings/${c.screening_id}`)}
                        className="text-xs px-3 py-1.5 rounded-lg bg-slate-200 text-slate-700 hover:bg-slate-300 transition-colors"
                      >
                        Report
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
