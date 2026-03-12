import clsx from 'clsx';

export default function StatCard({ label, value, trend, color = 'blue', icon }) {
  const colorMap = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    orange: 'bg-orange-50 text-orange-700 border-orange-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
  };

  return (
    <div className={clsx('rounded-xl border p-5', colorMap[color] || colorMap.blue)}>
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium opacity-80">{label}</p>
        {icon && <span className="text-2xl">{icon}</span>}
      </div>
      <p className="text-3xl font-bold mt-2">{value ?? '—'}</p>
      {trend !== undefined && (
        <p className={clsx('text-xs mt-1', trend >= 0 ? 'text-green-600' : 'text-red-600')}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}% from yesterday
        </p>
      )}
    </div>
  );
}
