import { useEffect, useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import { useSocket } from '../hooks/useSocket';
import StatCard from '../components/StatCard';
import toast from 'react-hot-toast';
import api from '../api';

export default function Overview() {
  const { data: overview, loading } = useFetch('/admin/overview/');
  const { data: health } = useFetch('/admin/overview/health');
  const [realtimeDetections, setRealtimeDetections] = useState(0);
  const [dataset, setDataset] = useState('all');
  const [exporting, setExporting] = useState(false);

  const { on } = useSocket('/admin-stream', ['detections', 'alerts']);

  useEffect(() => {
    on('new_detection', () => setRealtimeDetections((p) => p + 1));
    on('alert', (data) => toast.error(`Alert: ${data.message}`));
  }, [on]);

  if (loading) return <div className="animate-pulse">Loading overview...</div>;

  const o = overview || {};

  const onExportPdf = async () => {
    try {
      setExporting(true);
      const res = await api.get('/admin/export/pdf', {
        params: { dataset, limit: 1000 },
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `apis-${dataset}-export.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('PDF export downloaded');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to export PDF');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-bold">System Overview</h2>
        <div className="flex items-center gap-2">
          <select
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
            className="rounded-md border px-3 py-2 text-sm"
          >
            <option value="all">All data</option>
            <option value="potholes">Potholes</option>
            <option value="complaints">Complaints</option>
            <option value="scans">Scans</option>
            <option value="source_reports">Source reports</option>
          </select>
          <button
            type="button"
            onClick={onExportPdf}
            disabled={exporting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exporting ? 'Exporting...' : 'Export PDF'}
          </button>
        </div>
      </div>

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
