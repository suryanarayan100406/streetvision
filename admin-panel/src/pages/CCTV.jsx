import { useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function CCTV() {
  const { data: nodes, refetch } = useFetch('/admin/cctv/nodes');
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', rtsp_url: '', latitude: 0, longitude: 0, nh_number: '' });

  const addNode = async (e) => {
    e.preventDefault();
    await api.post('/admin/cctv/nodes', form);
    toast.success('CCTV node added');
    setShowAdd(false);
    refetch();
  };

  const testNode = async (id) => {
    try {
      const { data } = await api.post(`/admin/cctv/nodes/${id}/test`);
      toast.success(`Test: ${data.status} — ${data.resolution || ''}`);
    } catch {
      toast.error('RTSP connection failed');
    }
  };

  const toggleNode = async (id, active) => {
    if (active) {
      await api.delete(`/admin/cctv/nodes/${id}`);
      toast.success('Node deactivated');
    } else {
      await api.patch(`/admin/cctv/nodes/${id}`, { is_active: true });
      toast.success('Node activated');
    }
    refetch();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">CCTV Cameras</h2>
        <button onClick={() => setShowAdd(!showAdd)} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">
          + Add Camera
        </button>
      </div>

      {showAdd && (
        <form onSubmit={addNode} className="bg-white rounded-xl border p-4 mb-6 grid grid-cols-2 gap-4">
          <input placeholder="Camera Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border rounded px-3 py-2" required />
          <input placeholder="RTSP URL" value={form.rtsp_url} onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })} className="border rounded px-3 py-2 col-span-2" required />
          <input type="number" step="any" placeholder="Latitude" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: +e.target.value })} className="border rounded px-3 py-2" />
          <input type="number" step="any" placeholder="Longitude" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: +e.target.value })} className="border rounded px-3 py-2" />
          <input placeholder="NH Number" value={form.nh_number} onChange={(e) => setForm({ ...form, nh_number: e.target.value })} className="border rounded px-3 py-2" />
          <button type="submit" className="bg-green-600 text-white py-2 rounded-lg">Add Node</button>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {nodes?.map((n) => (
          <div key={n.id} className="bg-white rounded-xl border p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold">{n.name}</h3>
              <span className={`w-3 h-3 rounded-full ${n.is_active ? 'bg-green-500' : 'bg-red-500'}`} />
            </div>
            <p className="text-xs text-gray-500 truncate mb-1">{n.rtsp_url}</p>
            <p className="text-xs text-gray-500">{n.nh_number} — {n.latitude?.toFixed(4)}, {n.longitude?.toFixed(4)}</p>
            <div className="flex gap-2 mt-3">
              <button onClick={() => testNode(n.id)} className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">Test</button>
              <button onClick={() => toggleNode(n.id, n.is_active)} className="text-xs bg-gray-100 px-2 py-1 rounded">
                {n.is_active ? 'Deactivate' : 'Activate'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
