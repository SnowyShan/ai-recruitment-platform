import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { jobsAPI } from '../services/api';

// Recommendation badge colors
const REC_COLORS = {
  strong_yes: 'bg-green-100 text-green-700',
  yes: 'bg-teal-100 text-teal-700',
  maybe: 'bg-yellow-100 text-yellow-700',
  no: 'bg-red-100 text-red-700',
};

const REC_LABELS = {
  strong_yes: 'Strong Yes',
  yes: 'Yes',
  maybe: 'Maybe',
  no: 'No',
};

// Status badge colors
const STATUS_COLORS = {
  pending: 'bg-slate-100 text-slate-600',
  advanced: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
};

// Score badge component
function ScoreBadge({ score }) {
  if (score == null) return <span className="text-slate-300 text-sm">—</span>;
  const color = score >= 80 ? 'bg-green-100 text-green-700'
    : score >= 60 ? 'bg-yellow-100 text-yellow-700'
    : 'bg-red-100 text-red-700';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>
      {score}
    </span>
  );
}

// Stat card component
function StatCard({ label, value }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className="text-xl font-bold text-slate-900">{value}</div>
    </div>
  );
}

// Expandable candidate row component
function CandidateRow({ c, onStatusChange, onViewReport }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr
        className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
        onClick={() => setExpanded(v => !v)}
      >
        <td className="py-3 px-4 font-medium text-slate-900">
          {c.candidate_name}
          <span className="ml-2 text-slate-400 text-xs">{expanded ? '▲' : '▼'}</span>
        </td>
        <td className="py-3 px-4"><ScoreBadge score={c.overall_score} /></td>
        <td className="py-3 px-4"><ScoreBadge score={c.technical_score} /></td>
        <td className="py-3 px-4"><ScoreBadge score={c.communication_score} /></td>
        <td className="py-3 px-4"><ScoreBadge score={c.cultural_fit_score} /></td>
        <td className="py-3 px-4">
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${REC_COLORS[c.recommendation] || 'bg-slate-100 text-slate-500'}`}>
            {REC_LABELS[c.recommendation] || c.recommendation || '—'}
          </span>
        </td>
        <td className="py-3 px-4">
          <span className={`inline-block px-2 py-1 rounded-full text-sm font-semibold ${STATUS_COLORS[c.recruiter_status] || STATUS_COLORS.pending}`}>
            {c.recruiter_status === 'advanced' ? '✓ Advanced' :
             c.recruiter_status === 'rejected' ? '✗ Rejected' : 'Pending'}
          </span>
        </td>
        <td className="py-3 px-4 text-right" onClick={e => e.stopPropagation()}>
          <div className="flex items-center gap-2 justify-end">
            <button
              onClick={() => onStatusChange(c.screening_id, 'advanced')}
              className="text-xs px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-colors"
            >
              Advance
            </button>
            <button
              onClick={() => onStatusChange(c.screening_id, 'rejected')}
              className="text-xs px-3 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
            >
              Reject
            </button>
            <button
              onClick={() => onViewReport(c.screening_id)}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-200 text-slate-700 hover:bg-slate-300 transition-colors"
            >
              Report
            </button>
          </div>
        </td>
      </tr>

      {expanded && (
        <tr className="bg-slate-50 border-b border-slate-200">
          <td colSpan={8} className="px-6 py-4">
            {/* Summary */}
            {c.summary && (
              <p className="text-sm text-slate-700 mb-4 leading-relaxed">{c.summary}</p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {/* Strengths */}
              {c.strengths?.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Strengths</h4>
                  <ul className="space-y-1">
                    {c.strengths.map((s, i) => (
                      <li key={i} className="flex gap-2 text-sm text-slate-700">
                        <span className="text-green-500 flex-shrink-0">✓</span>{s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {/* Weaknesses */}
              {c.weaknesses?.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Gaps</h4>
                  <ul className="space-y-1">
                    {c.weaknesses.map((w, i) => (
                      <li key={i} className="flex gap-2 text-sm text-slate-700">
                        <span className="text-amber-500 flex-shrink-0">!</span>{w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Per-question breakdown */}
            {c.per_question?.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                  Question Breakdown
                </h4>
                <div className="space-y-2">
                  {c.per_question.map((q, i) => (
                    <div key={i} className="bg-white rounded-lg border border-slate-200 p-3">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <p className="text-xs text-slate-600 leading-relaxed flex-1">{q.question}</p>
                        <ScoreBadge score={q.score} />
                      </div>
                      {q.feedback && (
                        <p className="text-xs text-slate-500 mt-1">{q.feedback}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function InsightsDashboard() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cohortExpanded, setCohortExpanded] = useState(false);

  useEffect(() => {
    loadInsights();
  }, [jobId]);

  const loadInsights = async () => {
    try {
      const response = await jobsAPI.getInsights(jobId);
      setInsights(response.data);
    } catch (err) {
      console.error('Failed to load insights:', err);
    } finally {
      setLoading(false);
    }
  };

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

  const handleViewReport = (screeningId) => {
    navigate(`/screenings/${screeningId}`);
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

  const passCount = insights.candidates.filter(c =>
    c.recommendation === 'strong_yes' || c.recommendation === 'yes'
  ).length;
  const passRate = Math.round(passCount / insights.candidate_count * 100);

  return (
    <div className="min-h-screen bg-slate-50 p-4 sm:p-6 max-w-7xl mx-auto">
      <button onClick={() => navigate(-1)} className="btn btn-secondary mb-6">
        ← Back
      </button>

      <h1 className="text-3xl font-bold text-slate-900 mb-1">Hiring Insights</h1>
      <p className="text-slate-500 mb-6">
        Comprehensive analysis of candidate interviews
      </p>

      {/* Section 1: Summary bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Candidates" value={insights.candidate_count} />
        <StatCard label="Avg Score" value={`${insights.average_score}/100`} />
        <StatCard label="Pass Rate" value={`${passRate}%`} />
        <div className="card p-4 md:col-span-1">
          <div className="text-xs text-slate-500 mb-1">Cohort Verdict</div>
          <div className="text-sm font-medium text-slate-800">
            {insights.cohort_summary?.hiring_recommendation || '—'}
          </div>
        </div>
      </div>

      {/* Section 2: Candidate comparison table */}
      <section className="card p-6 mb-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Candidates (ranked by score)</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr className="text-left border-b border-slate-200 bg-slate-50">
                <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Candidate</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Overall</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Technical</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Communication</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Culture Fit</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Recommendation</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Status</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {insights.candidates.map((c) => (
                <CandidateRow
                  key={c.screening_id}
                  c={c}
                  onStatusChange={handleStatusChange}
                  onViewReport={handleViewReport}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Section 3: Cohort analysis (collapsible) */}
      <section className="card p-6">
        <button
          onClick={() => setCohortExpanded(v => !v)}
          className="w-full flex items-center justify-between text-left"
        >
          <h2 className="text-xl font-semibold text-slate-900">Cohort Analysis</h2>
          <span className="text-slate-400">{cohortExpanded ? '▲' : '▼'}</span>
        </button>

        {cohortExpanded && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
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
        )}
      </section>
    </div>
  );
}
