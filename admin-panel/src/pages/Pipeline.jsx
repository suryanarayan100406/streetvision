import { useEffect, useMemo } from 'react';
import { useFetch } from '../hooks/useFetch';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import StatCard from '../components/StatCard';

export default function Pipeline() {
  const statusQuery = useFetch('/admin/pipeline/status');
  const queuesQuery = useFetch('/admin/pipeline/queue-depths');
  const throughputQuery = useFetch('/admin/pipeline/throughput?hours=24');
  const historyQuery = useFetch('/admin/pipeline/task-history?limit=20');

  useEffect(() => {
    const intervalId = setInterval(() => {
      statusQuery.refetch();
      queuesQuery.refetch();
      throughputQuery.refetch();
      historyQuery.refetch();
    }, 15000);

    return () => clearInterval(intervalId);
  }, [statusQuery.refetch, queuesQuery.refetch, throughputQuery.refetch, historyQuery.refetch]);

  const status = statusQuery.data;
  const queues = queuesQuery.data;
  const throughput = throughputQuery.data;
  const taskHistory = historyQuery.data;

  const queueTotal = queues ? Object.values(queues).reduce((sum, depth) => sum + Number(depth || 0), 0) : 0;
  const activeSatellite = Object.entries(status?.satellite_jobs_24h || {}).reduce((sum, [name, count]) => {
    return sum + (['PENDING', 'RUNNING', 'PROCESSING'].includes(name) ? Number(count || 0) : 0);
  }, 0);
  const activeDrone = Object.entries(status?.drone_missions_24h || {}).reduce((sum, [name, count]) => {
    return sum + (['PENDING', 'RUNNING', 'PROCESSING', 'UPLOADED'].includes(name) ? Number(count || 0) : 0);
  }, 0);

  const throughputChartData = useMemo(() => {
    return (throughput || []).map((item) => ({
      ...item,
      hourLabel: new Date(item.hour).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }));
  }, [throughput]);

  const hasError = statusQuery.error || queuesQuery.error || throughputQuery.error || historyQuery.error;

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Pipeline Monitor</h2>
          <p className="text-sm text-gray-500 mt-1">Auto-refreshes every 15 seconds using backend pipeline metrics and recent task history.</p>
        </div>
        <button onClick={() => { statusQuery.refetch(); queuesQuery.refetch(); throughputQuery.refetch(); historyQuery.refetch(); }} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">
          Refresh
        </button>
      </div>

      {hasError && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Pipeline monitor is partially degraded. {statusQuery.error || queuesQuery.error || throughputQuery.error || historyQuery.error}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4 mb-8">
        <StatCard label="Detections (1h)" value={status?.detections_last_hour} icon="🔍" color="blue" />
        <StatCard label="Detections (24h)" value={status?.detections_last_24h} icon="📊" color="blue" />
        <StatCard label="Complaints (24h)" value={status?.complaints_last_24h} icon="📄" color="purple" />
        <StatCard label="Active Satellite Jobs" value={activeSatellite} icon="🛰️" color="orange" />
        <StatCard label="Active Drone Missions" value={activeDrone} icon="🚁" color="purple" />
        <StatCard label="Queue Total" value={queueTotal} icon="📬" color="orange" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl border p-4">
          <h3 className="text-lg font-semibold mb-3">Satellite Status (24h)</h3>
          {status?.satellite_jobs_24h && Object.keys(status.satellite_jobs_24h).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(status.satellite_jobs_24h).map(([name, count]) => (
                <span key={name} className="px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-sm">
                  {name}: {count}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No satellite jobs in the last 24 hours.</p>
          )}
        </div>

        <div className="bg-white rounded-xl border p-4">
          <h3 className="text-lg font-semibold mb-3">Drone Status (24h)</h3>
          {status?.drone_missions_24h && Object.keys(status.drone_missions_24h).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(status.drone_missions_24h).map(([name, count]) => (
                <span key={name} className="px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-sm">
                  {name}: {count}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No drone missions in the last 24 hours.</p>
          )}
        </div>
      </div>

      <h3 className="text-lg font-semibold mb-3">Queue Depths</h3>
      <div className="grid grid-cols-4 lg:grid-cols-7 gap-3 mb-8">
        {queues && Object.entries(queues).map(([name, depth]) => (
          <div key={name} className="bg-white rounded-lg border p-3 text-center">
            <p className="text-2xl font-bold">{depth}</p>
            <p className="text-xs text-gray-500 mt-1">{name}</p>
          </div>
        ))}
      </div>

      <h3 className="text-lg font-semibold mb-3">Hourly Throughput</h3>
      <div className="bg-white rounded-xl border p-4 mb-8" style={{ height: 300 }}>
        {throughputChartData?.length ? (
          <ResponsiveContainer>
            <BarChart data={throughputChartData}>
              <XAxis dataKey="hourLabel" tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-sm text-gray-400">
            No task throughput history available yet.
          </div>
        )}
      </div>

      <h3 className="text-lg font-semibold mb-3">Recent Task Feed</h3>
      <div className="bg-white rounded-xl border max-h-64 overflow-y-auto">
        {!taskHistory || taskHistory.length === 0 ? (
          <p className="p-4 text-gray-400 text-sm">No recent task history recorded yet.</p>
        ) : (
          <div className="divide-y">
            {taskHistory.map((task) => (
              <div key={task.id} className="px-4 py-3 text-sm flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-800">{task.task_name || 'Unknown task'}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {task.completed_at ? new Date(task.completed_at).toLocaleString() : 'No completion time'}
                    {task.duration_seconds ? ` • ${Number(task.duration_seconds).toFixed(2)}s` : ''}
                  </p>
                </div>
                <span className={`px-2 py-1 rounded text-xs font-medium ${task.status === 'SUCCESS' ? 'bg-green-100 text-green-700' : task.status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                  {task.status || 'UNKNOWN'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
