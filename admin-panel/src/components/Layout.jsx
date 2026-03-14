import { NavLink, Outlet } from 'react-router-dom';
import clsx from 'clsx';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: '📊' },
  { to: '/satellites', label: 'Satellites', icon: '🛰️' },
  { to: '/drones', label: 'Drones', icon: '🚁' },
  { to: '/cctv', label: 'CCTV', icon: '📹' },
  { to: '/pipeline', label: 'Pipeline', icon: '⚙️' },
  { to: '/pipeline-test', label: 'Pipeline Test', icon: '🧪' },
  { to: '/detections', label: 'Detections', icon: '🕳️' },
  { to: '/models', label: 'ML Models', icon: '🧠' },
  { to: '/scheduler', label: 'Scheduler', icon: '🕐' },
  { to: '/settings', label: 'Settings', icon: '⚡' },
  { to: '/logs', label: 'Logs', icon: '📋' },
  { to: '/module-detection-output', label: 'Module · Detection', icon: '🧩' },
  { to: '/module-model-predictions', label: 'Module · Predictions', icon: '🧩' },
  { to: '/module-escalation-logic', label: 'Module · Escalation', icon: '🧩' },
  { to: '/module-compiled-pipeline', label: 'Module · Compiled', icon: '🧩' },
];

export default function Layout() {
  const handleLogout = () => {
    localStorage.clear();
    window.location.href = '/login';
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-lg font-bold">🛣️ Pothole Intel</h1>
          <p className="text-xs text-gray-400 mt-1">Admin Control Panel</p>
        </div>
        <nav className="flex-1 overflow-y-auto py-4">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                  isActive
                    ? 'bg-primary-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                )
              }
            >
              <span>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-700">
          <button
            onClick={handleLogout}
            className="w-full text-sm text-gray-400 hover:text-white transition-colors"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-50 p-6">
        <Outlet />
      </main>
    </div>
  );
}
