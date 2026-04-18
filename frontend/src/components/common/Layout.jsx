import { useState, useEffect, useRef, useCallback } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import {
  Bell, Search, Menu, CheckCircle2, UserPlus, ChevronRight, X,
  Briefcase, Users, FileText, ArrowRight
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { dashboardAPI, jobsAPI, candidatesAPI, applicationsAPI } from '../../services/api';

/* ── Global Search Component ──────────────────────────────────────────────── */
const GlobalSearch = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState({ jobs: [], candidates: [], applications: [] });
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef(null);
  const debounceRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Keyboard shortcut: Cmd/Ctrl + K
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const input = wrapperRef.current?.querySelector('input');
        input?.focus();
      }
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const doSearch = useCallback(async (term) => {
    if (!term || term.length < 2) {
      setResults({ jobs: [], candidates: [], applications: [] });
      setIsOpen(false);
      return;
    }

    setLoading(true);
    try {
      const [jobsRes, candidatesRes, appsRes] = await Promise.allSettled([
        jobsAPI.getAll({ search: term, limit: 5 }),
        candidatesAPI.getAll({ search: term, limit: 5 }),
        applicationsAPI.getAll({ search: term, limit: 5 }),
      ]);

      setResults({
        jobs: jobsRes.status === 'fulfilled' ? (jobsRes.value.data || []).slice(0, 5) : [],
        candidates: candidatesRes.status === 'fulfilled' ? (candidatesRes.value.data || []).slice(0, 5) : [],
        applications: appsRes.status === 'fulfilled' ? (appsRes.value.data || []).slice(0, 5) : [],
      });
      setIsOpen(true);
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = (e) => {
    const val = e.target.value;
    setQuery(val);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val), 300);
  };

  const handleSelect = (type, item) => {
    setIsOpen(false);
    setQuery('');
    if (type === 'job') navigate(`/jobs/${item.id}`);
    else if (type === 'candidate') navigate('/candidates');
    else if (type === 'application') navigate('/applications');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && query.length >= 2) {
      setIsOpen(false);
      // Navigate to the most relevant section
      if (results.jobs.length > 0) navigate(`/jobs?search=${encodeURIComponent(query)}`);
      else if (results.applications.length > 0) navigate(`/applications?search=${encodeURIComponent(query)}`);
      else if (results.candidates.length > 0) navigate(`/candidates?search=${encodeURIComponent(query)}`);
    }
  };

  const totalResults = results.jobs.length + results.candidates.length + results.applications.length;

  return (
    <div ref={wrapperRef} className="relative flex-1 hidden sm:block">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length >= 2 && totalResults > 0 && setIsOpen(true)}
          placeholder="Search jobs, candidates, applications... (⌘K)"
          className="w-full pl-12 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
        />
        {loading && (
          <div className="absolute right-4 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-slate-300 border-t-primary-500 rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Search Results Dropdown */}
      {isOpen && (
        <div className="absolute top-12 left-0 right-0 bg-white rounded-2xl border border-slate-200 shadow-xl z-50 overflow-hidden max-h-[480px] overflow-y-auto">
          {totalResults === 0 && !loading ? (
            <div className="p-6 text-center text-slate-400">
              <Search className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No results found for "{query}"</p>
            </div>
          ) : (
            <>
              {/* Jobs */}
              {results.jobs.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-slate-50 border-b border-slate-100">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      <Briefcase className="w-3.5 h-3.5" />
                      Jobs ({results.jobs.length})
                    </div>
                  </div>
                  {results.jobs.map((job) => (
                    <button
                      key={`job-${job.id}`}
                      onClick={() => handleSelect('job', job)}
                      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors text-left"
                    >
                      <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Briefcase className="w-4 h-4 text-blue-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-900 truncate">{job.title}</p>
                        <p className="text-xs text-slate-400 truncate">
                          {[job.department, job.location].filter(Boolean).join(' · ') || 'No details'}
                        </p>
                      </div>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        job.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                      }`}>{job.status}</span>
                      <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
                    </button>
                  ))}
                </div>
              )}

              {/* Candidates */}
              {results.candidates.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-slate-50 border-b border-slate-100">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      <Users className="w-3.5 h-3.5" />
                      Candidates ({results.candidates.length})
                    </div>
                  </div>
                  {results.candidates.map((candidate) => (
                    <button
                      key={`cand-${candidate.id}`}
                      onClick={() => handleSelect('candidate', candidate)}
                      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors text-left"
                    >
                      <div className="w-8 h-8 bg-purple-50 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Users className="w-4 h-4 text-purple-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-900 truncate">{candidate.full_name}</p>
                        <p className="text-xs text-slate-400 truncate">{candidate.email}</p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
                    </button>
                  ))}
                </div>
              )}

              {/* Applications */}
              {results.applications.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-slate-50 border-b border-slate-100">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      <FileText className="w-3.5 h-3.5" />
                      Applications ({results.applications.length})
                    </div>
                  </div>
                  {results.applications.map((app) => (
                    <button
                      key={`app-${app.id}`}
                      onClick={() => handleSelect('application', app)}
                      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors text-left"
                    >
                      <div className="w-8 h-8 bg-indigo-50 rounded-lg flex items-center justify-center flex-shrink-0">
                        <FileText className="w-4 h-4 text-indigo-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-900 truncate">
                          {app.candidate?.full_name || 'Unknown'} → {app.job?.title || 'Unknown'}
                        </p>
                        <p className="text-xs text-slate-400">
                          {app.match_score != null ? `Score: ${Math.round(app.match_score)}%` : 'No score'} · {app.status}
                        </p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
                    </button>
                  ))}
                </div>
              )}

              {/* View All link */}
              {totalResults > 0 && (
                <div className="border-t border-slate-100 px-4 py-2.5">
                  <button
                    onClick={() => {
                      setIsOpen(false);
                      if (results.jobs.length > 0) navigate(`/jobs?search=${encodeURIComponent(query)}`);
                      else navigate('/applications');
                    }}
                    className="w-full text-xs text-primary-600 hover:text-primary-700 font-medium text-center py-1 flex items-center justify-center gap-1"
                  >
                    View all results <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

/* ── Layout Component ─────────────────────────────────────────────────────── */
const Layout = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifLoading, setNotifLoading] = useState(false);
  const bellRef = useRef(null);
  const dropRef = useRef(null);

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClick = (e) => {
      if (notifOpen && dropRef.current && !dropRef.current.contains(e.target) && !bellRef.current.contains(e.target)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [notifOpen]);

  const loadNotifications = async () => {
    try {
      setNotifLoading(true);
      const res = await dashboardAPI.getNotifications();
      setNotifications(res.data.notifications || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch (_) {}
    finally { setNotifLoading(false); }
  };

  const handleNotifClick = (notif) => {
    setNotifOpen(false);
    navigate(notif.link || '/dashboard');
  };

  const typeIcon = (type) => {
    if (type === 'screening_complete') return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    return <UserPlus className="w-4 h-4 text-blue-500" />;
  };

  const scoreColor = (score, rec) => {
    if (!score) return '';
    if (rec === 'pass') return 'text-emerald-600 font-semibold';
    if (rec === 'fail') return 'text-red-500 font-semibold';
    return score >= 80 ? 'text-emerald-600 font-semibold' : score >= 60 ? 'text-amber-600 font-semibold' : 'text-red-500 font-semibold';
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="lg:pl-64">
        <header className="h-16 bg-white border-b border-slate-200 sticky top-0 z-30">
          <div className="h-full px-4 sm:px-8 flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors flex-shrink-0"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Replaced static input with working GlobalSearch */}
            <GlobalSearch />

            <div className="flex-1 sm:hidden" />

            <div className="flex items-center gap-2 sm:gap-3">
              {/* Notification bell */}
              <div className="relative">
                <button
                  ref={bellRef}
                  onClick={() => setNotifOpen(o => !o)}
                  className="relative p-2.5 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors"
                >
                  <Bell className="w-5 h-5" />
                  {unreadCount > 0 && (
                    <span className="absolute top-1.5 right-1.5 w-4 h-4 bg-red-500 rounded-full text-white text-[9px] font-bold flex items-center justify-center">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </button>

                {/* Notification dropdown */}
                {notifOpen && (
                  <div
                    ref={dropRef}
                    className="absolute right-0 top-12 w-96 bg-white rounded-2xl border border-slate-200 shadow-xl z-50 overflow-hidden"
                  >
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900">Notifications</h3>
                        {unreadCount > 0 && <p className="text-xs text-slate-400 mt-0.5">{unreadCount} new updates</p>}
                      </div>
                      <button onClick={() => setNotifOpen(false)} className="p-1.5 rounded-lg hover:bg-slate-100">
                        <X className="w-4 h-4 text-slate-400" />
                      </button>
                    </div>

                    <div className="divide-y divide-slate-50 max-h-[420px] overflow-y-auto">
                      {notifLoading && notifications.length === 0 ? (
                        <div className="p-6 text-center"><div className="spinner mx-auto" /></div>
                      ) : notifications.length === 0 ? (
                        <div className="p-8 text-center text-slate-400">
                          <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
                          <p className="text-sm">No notifications yet</p>
                          <p className="text-xs mt-1">Screening completions will appear here</p>
                        </div>
                      ) : notifications.map((n) => (
                        <button
                          key={n.id}
                          onClick={() => handleNotifClick(n)}
                          className="w-full flex items-start gap-3 px-4 py-3.5 hover:bg-slate-50 transition-colors text-left"
                        >
                          <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                            {typeIcon(n.type)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-slate-900 truncate">{n.title}</p>
                            <p className="text-xs text-slate-500 mt-0.5 truncate">{n.body}</p>
                            {n.score && (
                              <p className={`text-xs mt-1 ${scoreColor(n.score, n.recommendation)}`}>
                                Score: {n.score}/100 · {n.recommendation === 'pass' ? '✓ Recommended' : n.recommendation === 'fail' ? '✗ Not recommended' : ''}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-col items-end gap-1 flex-shrink-0">
                            <span className="text-xs text-slate-400">{n.time}</span>
                            {!n.read && <span className="w-2 h-2 bg-blue-500 rounded-full" />}
                            <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
                          </div>
                        </button>
                      ))}
                    </div>

                    {notifications.length > 0 && (
                      <div className="border-t border-slate-100 px-4 py-2.5">
                        <button
                          onClick={() => { setNotifOpen(false); navigate('/screenings'); }}
                          className="w-full text-xs text-primary-600 hover:text-primary-700 font-medium text-center py-1"
                        >
                          View all screenings →
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="w-9 h-9 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center text-white font-semibold cursor-pointer hover:shadow-lg transition-shadow flex-shrink-0 text-sm">
                {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
              </div>
            </div>
          </div>
        </header>

        <main className="p-4 sm:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
