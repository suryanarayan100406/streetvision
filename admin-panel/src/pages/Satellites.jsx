import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function Satellites() {
  const { data: sources, refetch } = useFetch('/admin/satellites/sources');
  const { data: jobs } = useFetch('/admin/satellites/jobs?limit=20');

  const toggleSource = async (id, enabled) => {
    await api.patch(`/admin/satellites/sources/${id}`, { enabled: !enabled });
    toast.success(`Source ${!enabled ? 'enabled' : 'disabled'}`);
    refetch();
  };

  const testConnection = async (id) => {
    try {
      const { data } = await api.post(`/admin/satellites/sources/${id}/test`);
      toast.success(`Connection: ${data.status}`);
    } catch {
      toast.error('Connection test failed');
    }
  };

  const triggerIngestion = async (name) => {
    const { data } = await api.post(`/admin/satellites/trigger/${name}`);
    toast.success(`Triggered: ${data.task_id}`);
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Satellite Sources</h2>

      {/* Sources table */}
      <div className="bg-white rounded-xl border overflow-hidden mb-8">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Source</th>
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-left px-4 py-3">Priority</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Last Success</th>
              <th className="text-left px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {sources?.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{s.name}</td>
                <td className="px-4 py-3">{s.source_type}</td>
                <td className="px-4 py-3">{s.priority}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${s.enabled ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {s.enabled ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">{s.last_successful_at || '—'}</td>
                <td className="px-4 py-3 flex gap-2">
                  <button onClick={() => toggleSource(s.id, s.enabled)} className="text-xs bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded">
                    {s.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button onClick={() => testConnection(s.id)} className="text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 px-2 py-1 rounded">
                    Test
                  </button>
                  <button onClick={() => triggerIngestion(s.name)} className="text-xs bg-primary-100 hover:bg-primary-200 text-primary-700 px-2 py-1 rounded">
                    Trigger
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent jobs */}
      <h3 className="text-lg font-semibold mb-3">Recent Jobs</h3>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">ID</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Tiles</th>
              <th className="text-left px-4 py-3">Detections</th>
              <th className="text-left px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {jobs?.map((j) => (
              <tr key={j.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">{j.id}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${j.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : j.status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                    {j.status}
                  </span>
                </td>
                <td className="px-4 py-3">{j.tiles_processed}/{j.tiles_total}</td>
                <td className="px-4 py-3">{j.detections_count}</td>
                <td className="px-4 py-3 text-gray-500">{j.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
