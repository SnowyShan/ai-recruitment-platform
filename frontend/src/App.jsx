import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import Layout from './components/common/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Candidates from './pages/Candidates';
import Applications from './pages/Applications';
import Screenings from './pages/Screenings';
import BrowseJobs from './pages/BrowseJobs';
import ApplyJob from './pages/ApplyJob';
import CandidateStatus from './pages/CandidateStatus';
import JobDetail from './pages/JobDetail';
import Settings from './pages/Settings';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Protected routes */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/jobs/:id" element={<JobDetail />} />
            <Route path="/candidates" element={<Candidates />} />
            <Route path="/applications" element={<Applications />} />
            <Route path="/screenings" element={<Screenings />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/help" element={<Help />} />
          </Route>
          
          {/* Public candidate routes (no auth, no Layout) */}
          <Route path="/browse-jobs" element={<BrowseJobs />} />
          <Route path="/browse-jobs/:id" element={<ApplyJob />} />
          <Route path="/my-applications" element={<CandidateStatus />} />

          {/* Redirect root to dashboard */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* 404 catch-all */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

// Simple placeholder pages
const Help = () => (
  <div className="space-y-6 animate-fade-in">
    <h1 className="text-3xl font-bold text-slate-900">Help & Support</h1>
    <div className="card p-8 text-center">
      <p className="text-slate-500">Help documentation coming soon...</p>
    </div>
  </div>
);

const NotFound = () => (
  <div className="min-h-screen flex items-center justify-center bg-slate-50">
    <div className="text-center">
      <h1 className="text-6xl font-bold text-slate-300 mb-4">404</h1>
      <p className="text-xl text-slate-600 mb-6">Page not found</p>
      <a href="/dashboard" className="btn btn-primary">Go to Dashboard</a>
    </div>
  </div>
);

export default App;
