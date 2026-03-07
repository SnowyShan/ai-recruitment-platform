import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { Bell, Search, Plus, Menu } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const Layout = () => {
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content area — offset by sidebar width on large screens */}
      <div className="lg:pl-64">
        {/* Top header */}
        <header className="h-16 bg-white border-b border-slate-200 sticky top-0 z-30">
          <div className="h-full px-4 sm:px-8 flex items-center gap-3">
            {/* Hamburger — mobile/tablet only */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors flex-shrink-0"
              aria-label="Open menu"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Search — hidden on small screens */}
            <div className="flex-1 max-w-xl hidden sm:block">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search jobs, candidates, applications..."
                  className="w-full pl-12 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                />
              </div>
            </div>

            {/* Spacer on mobile (pushes actions to the right) */}
            <div className="flex-1 sm:hidden" />

            {/* Actions */}
            <div className="flex items-center gap-2 sm:gap-4">
              <button className="btn btn-primary hidden sm:inline-flex">
                <Plus className="w-4 h-4" />
                New Job
              </button>

              {/* New Job icon-only on mobile */}
              <button className="sm:hidden p-2 rounded-xl bg-primary-600 text-white hover:bg-primary-700 transition-colors">
                <Plus className="w-5 h-5" />
              </button>

              <button className="relative p-2.5 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors">
                <Bell className="w-5 h-5" />
                <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full"></span>
              </button>

              <div className="w-10 h-10 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center text-white font-semibold cursor-pointer hover:shadow-lg transition-shadow flex-shrink-0">
                {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
