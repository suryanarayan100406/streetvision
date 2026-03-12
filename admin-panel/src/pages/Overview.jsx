import { useEffect, useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import { useSocket } from '../hooks/useSocket';
import StatCard from '../components/StatCard';
import toast from 'react-hot-toast';

export default function Overview() {
  const { data: overview, loading } = useFetch('/admin/overview/');
  const { data: health } = useFetch('/admin/overview/health');
  const [realtimeDetections, setRealtimeDetections] = useState(0);

  const { on } = useSocket('/admin-stream', ['detections', 'alerts']);

  useEffect(() => {
    on('new_detection', () => setRealtimeDetections((p) => p + 1));
    on('alert', (data) => toast.error(`Alert: ${data.message}`));
  }, [on]);

  if (loading) return <div className="animate-pulse">Loading overview...</div>;

  const o = overview || {};

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">System Overview</h2>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Potholes" value={o.total_potholes} icon="🕳️" color="blue" />
        <StatCard label="Active" value={o.active_potholes} icon="🔴" color="orange" />
        <StatCard label="Critical" value={o.critical_potholes} icon="⚠️" color="red" />
        <StatCard label="New (24h)" value={o.new_last_24h} icon="🆕" color="green" />
        <StatCard label="Complaints Filed" value={o.total_complaints} icon="📄" color="purple" />
        <StatCard label="Open Complaints" value={o.open_complaints} icon="📬" color="orange" />
        <StatCard label="Critically Overdue" value={o.critically_overdue} icon="🚨" color="red" />
        <StatCard label="Live Detections" value={realtimeDetections} icon="📡" color="green" />
      </div>

      {/* Infrastructure status */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard label="Satellite Jobs" value={o.active_satellite_jobs} icon="🛰️" color="blue" />
        <StatCard label="Drone Missions" value={o.active_drone_missions} icon="🚁" color="blue" />
        <StatCard label="Active CCTV" value={o.active_cctv_cameras} icon="📹" color="blue" />
      </div>

      {/* Health checks */}
      <h3 className="text-lg font-semibold mb-3">System Health</h3>
      {health && (
        <div className="bg-white rounded-xl border p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className={`w-3 h-3 rounded-full ${health.overall === 'healthy' ? 'bg-green-500' : health.overall === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'}`} />
            <span className="font-medium capitalize">{health.overall}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {health.checks?.map((c) => (
              <div key={c.name} className="flex items-center gap-2 text-sm">
                <span className={`w-2 h-2 rounded-full ${c.status === 'healthy' ? 'bg-green-500' : c.status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'}`} />
                {c.name}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
