import { Link, useLocation, Outlet } from 'react-router-dom';
import clsx from 'clsx';

export default function Layout({ children }) {
  const { pathname } = useLocation();

  const navItems = [
    { label: 'Map', path: '/', icon: '🗺️' },
    { label: 'Kanban', path: '/kanban', icon: '📋' },
    { label: 'Leaderboard', path: '/leaderboard', icon: '🏆' },
    { label: 'Analytics', path: '/analytics', icon: '📊' },
  ];

  return (
    <div className="flex h-screen bg-gray-50">
      <nav className="w-64 bg-white border-r border-gray-200 shadow-sm">
        <div className="p-6 border-b border-gray-200">
          <h1 className="text-xl font-bold text-gray-900">🛣️ CG Pothole</h1>
          <p className="text-xs text-gray-500 mt-1">Chhattisgarh Tracker</p>
        </div>
        <menu className="space-y-1 p-4">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={clsx(
                'block px-4 py-2 rounded-lg transition',
                pathname === item.path
                  ? 'bg-blue-100 text-blue-900 font-semibold'
                  : 'text-gray-700 hover:bg-gray-100'
              )}
            >
              {item.icon} {item.label}
            </Link>
          ))}
        </menu>
        <div className="absolute bottom-4 left-4 right-4 text-xs text-gray-500 p-3 bg-gray-50 rounded">
          <p>📍 NT-Route: NH-30, NH-53, NH-130C</p>
        </div>
      </nav>
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-6">
          {children}
          <Outlet />
        </div>
      </main>
    </div>
  );
}
