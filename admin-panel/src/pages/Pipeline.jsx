import { useFetch } from '../hooks/useFetch';
import { useSocket } from '../hooks/useSocket';
import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import StatCard from '../components/StatCard';

export default function Pipeline() {
  const { data: status } = useFetch('/admin/pipeline/status');
  const { data: queues } = useFetch('/admin/pipeline/queue-depths');
  const { data: throughput } = useFetch('/admin/pipeline/throughput?hours=24');
  const [taskUpdates, setTaskUpdates] = useState([]);

  const { on } = useSocket('/admin-stream', ['tasks']);

  useEffect(() => {
    on('task_update', (data) => {
      setTaskUpdates((prev) => [data, ...prev].slice(0, 50));
    });
  }, [on]);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Pipeline Monitor</h2>

      {/* Status cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Detections (1h)" value={status?.detections_last_hour} icon="🔍" color="blue" />
        <StatCard label="Detections (24h)" value={status?.detections_last_24h} icon="📊" color="blue" />
        <StatCard label="Complaints (24h)" value={status?.complaints_last_24h} icon="📄" color="purple" />
        <StatCard label="Queue Total" value={queues ? Object.values(queues).reduce((a, b) => a + b, 0) : 0} icon="📬" color="orange" />
      </div>

      {/* Queue depths */}
      <h3 className="text-lg font-semibold mb-3">Queue Depths</h3>
      <div className="grid grid-cols-4 lg:grid-cols-7 gap-3 mb-8">
        {queues && Object.entries(queues).map(([name, depth]) => (
          <div key={name} className="bg-white rounded-lg border p-3 text-center">
            <p className="text-2xl font-bold">{depth}</p>
            <p className="text-xs text-gray-500 mt-1">{name}</p>
          </div>
        ))}
      </div>

      {/* Throughput chart */}
      <h3 className="text-lg font-semibold mb-3">Hourly Throughput</h3>
      <div className="bg-white rounded-xl border p-4 mb-8" style={{ height: 300 }}>
        <ResponsiveContainer>
          <BarChart data={throughput || []}>
            <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Live task feed */}
      <h3 className="text-lg font-semibold mb-3">Live Task Feed</h3>
      <div className="bg-white rounded-xl border max-h-64 overflow-y-auto">
        {taskUpdates.length === 0 ? (
          <p className="p-4 text-gray-400 text-sm">Waiting for task updates...</p>
        ) : (
          <div className="divide-y">
            {taskUpdates.map((t, i) => (
              <div key={i} className="px-4 py-2 text-sm flex justify-between">
                <span>{t.task_name || t.task}</span>
                <span className="text-gray-400">{t.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
