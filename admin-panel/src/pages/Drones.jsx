import { useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function Drones() {
  const { data: missions, refetch } = useFetch('/admin/drones/missions?limit=30');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ mission_name: '', operator: '', image_count: 0, gsd_cm: 2.0 });
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadForm, setUploadForm] = useState({
    mission_name: '',
    operator: '',
    flight_date: '',
    area_bbox: '',
    image_count: 1,
    gsd_cm: 2.0,
    auto_process: true,
  });
  const [uploadFile, setUploadFile] = useState(null);

  const createMission = async (e) => {
    e.preventDefault();
    await api.post('/admin/drones/missions', form);
    toast.success('Mission created & processing queued');
    setShowCreate(false);
    refetch();
  };

  const reprocess = async (id) => {
    await api.post(`/admin/drones/missions/${id}/reprocess`);
    toast.success('Reprocessing triggered');
    refetch();
  };

  const uploadMission = async (e) => {
    e.preventDefault();
    if (!uploadFile) {
      toast.error('Please choose a file');
      return;
    }

    const fd = new FormData();
    fd.append('file', uploadFile);
    if (uploadForm.mission_name) fd.append('mission_name', uploadForm.mission_name);
    if (uploadForm.operator) fd.append('operator', uploadForm.operator);
    if (uploadForm.flight_date) fd.append('flight_date', uploadForm.flight_date);
    if (uploadForm.area_bbox) fd.append('area_bbox', uploadForm.area_bbox);
    fd.append('image_count', String(uploadForm.image_count ?? 0));
    fd.append('gsd_cm', String(uploadForm.gsd_cm ?? 0));
    fd.append('auto_process', uploadForm.auto_process ? 'true' : 'false');

    try {
      setUploading(true);
      const { data } = await api.post('/admin/drones/missions/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success(data?.message || 'Upload successful');
      setUploadFile(null);
      setUploadForm({
        mission_name: '',
        operator: '',
        flight_date: '',
        area_bbox: '',
        image_count: 1,
        gsd_cm: 2.0,
        auto_process: true,
      });
      setShowUpload(false);
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Drone Missions</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowUpload(!showUpload)} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm">
            Upload Footage
          </button>
          <button onClick={() => setShowCreate(!showCreate)} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">
            + New Mission
          </button>
        </div>
      </div>

      {showUpload && (
        <form onSubmit={uploadMission} className="bg-white rounded-xl border p-4 mb-6 grid grid-cols-2 gap-4">
          <input type="file" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} className="col-span-2 border rounded px-3 py-2" accept=".zip,.jpg,.jpeg,.png,.tif,.tiff,.mp4,.mov,.mkv" required />
          <input placeholder="Mission Name" value={uploadForm.mission_name} onChange={(e) => setUploadForm({ ...uploadForm, mission_name: e.target.value })} className="border rounded px-3 py-2" />
          <input placeholder="Operator" value={uploadForm.operator} onChange={(e) => setUploadForm({ ...uploadForm, operator: e.target.value })} className="border rounded px-3 py-2" />
          <input type="date" value={uploadForm.flight_date} onChange={(e) => setUploadForm({ ...uploadForm, flight_date: e.target.value })} className="border rounded px-3 py-2" />
          <input type="number" step="0.1" placeholder="GSD (cm)" value={uploadForm.gsd_cm} onChange={(e) => setUploadForm({ ...uploadForm, gsd_cm: +e.target.value })} className="border rounded px-3 py-2" />
          <input type="number" placeholder="Image Count" value={uploadForm.image_count} onChange={(e) => setUploadForm({ ...uploadForm, image_count: +e.target.value })} className="border rounded px-3 py-2" />
          <input placeholder='Area BBox JSON (optional)' value={uploadForm.area_bbox} onChange={(e) => setUploadForm({ ...uploadForm, area_bbox: e.target.value })} className="border rounded px-3 py-2" />
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={uploadForm.auto_process} onChange={(e) => setUploadForm({ ...uploadForm, auto_process: e.target.checked })} />
            Auto process after upload (image files)
          </label>
          <button type="submit" disabled={uploading} className="col-span-2 bg-indigo-600 text-white py-2 rounded-lg disabled:opacity-60">
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </form>
      )}

      {showCreate && (
        <form onSubmit={createMission} className="bg-white rounded-xl border p-4 mb-6 grid grid-cols-2 gap-4">
          <input placeholder="Mission Name" value={form.mission_name} onChange={(e) => setForm({ ...form, mission_name: e.target.value })} className="border rounded px-3 py-2" required />
          <input placeholder="Operator" value={form.operator} onChange={(e) => setForm({ ...form, operator: e.target.value })} className="border rounded px-3 py-2" />
          <input type="number" placeholder="Image Count" value={form.image_count} onChange={(e) => setForm({ ...form, image_count: +e.target.value })} className="border rounded px-3 py-2" />
          <input type="number" step="0.1" placeholder="GSD (cm)" value={form.gsd_cm} onChange={(e) => setForm({ ...form, gsd_cm: +e.target.value })} className="border rounded px-3 py-2" />
          <button type="submit" className="col-span-2 bg-green-600 text-white py-2 rounded-lg">Create & Process</button>
        </form>
      )}

      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Mission</th>
              <th className="text-left px-4 py-3">Operator</th>
              <th className="text-left px-4 py-3">Images</th>
              <th className="text-left px-4 py-3">GSD</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {missions?.map((m) => (
              <tr key={m.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{m.mission_name}</td>
                <td className="px-4 py-3">{m.operator}</td>
                <td className="px-4 py-3">{m.image_count}</td>
                <td className="px-4 py-3">{m.gsd_cm} cm</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${m.processing_status === 'COMPLETED' ? 'bg-green-100 text-green-700' : m.processing_status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                    {m.processing_status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => reprocess(m.id)} className="text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 px-2 py-1 rounded">
                    Reprocess
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
