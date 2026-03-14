import { useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function ModuleDetectionOutput() {
  const { data: missions, refetch: refetchMissions } = useFetch('/admin/drones/missions?limit=20');
  const { data: pending, refetch: refetchPending } = useFetch('/admin/detections/pending?confidence_below=0.95&limit=25');

  const [uploading, setUploading] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [scenePreview, setScenePreview] = useState(null);

  const [uploadForm, setUploadForm] = useState({
    mission_name: '',
    operator: '',
    flight_date: '',
    area_bbox: '',
    image_count: 1,
    gsd_cm: 2.0,
    auto_process: true,
  });

  const [scanForm, setScanForm] = useState({
    source: 'SENTINEL-2',
    bbox: '',
    limit: 12,
    max_cloud: 20,
    date_from: '',
    date_to: '',
    forward_to_inference: true,
  });

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
      refetchMissions();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const previewSatelliteScenes = async () => {
    try {
      setScanLoading(true);
      const payload = {
        source: scanForm.source,
        bbox: scanForm.bbox,
        limit: Number(scanForm.limit),
        max_cloud: Number(scanForm.max_cloud),
        date_from: scanForm.date_from || null,
        date_to: scanForm.date_to || null,
        forward_to_inference: Boolean(scanForm.forward_to_inference),
      };
      const { data } = await api.post('/admin/satellites/search', payload);
      setScenePreview(data);
      toast.success(`Found ${data.count} scene(s)`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Satellite preview failed');
    } finally {
      setScanLoading(false);
    }
  };

  const triggerSatelliteScan = async () => {
    try {
      setScanLoading(true);
      const payload = {
        source: scanForm.source,
        bbox: scanForm.bbox,
        limit: Number(scanForm.limit),
        max_cloud: Number(scanForm.max_cloud),
        date_from: scanForm.date_from || null,
        date_to: scanForm.date_to || null,
        forward_to_inference: Boolean(scanForm.forward_to_inference),
      };
      const { data } = await api.post('/admin/satellites/scan', payload);
      toast.success(`Scan queued (job ${data.job_id})`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to queue scan');
    } finally {
      setScanLoading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module · Detection Execution</h2>
        <button onClick={() => { refetchMissions(); refetchPending(); }} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
      </div>
      <p className="text-sm text-gray-500 mb-6">Upload footage/images or trigger a satellite area scan. All outputs shown are live pipeline data.</p>

      <div className="bg-white border rounded-xl p-4 mb-6">
        <h3 className="font-semibold mb-3">A) Upload Drone Footage / Images</h3>
        <form onSubmit={uploadMission} className="grid grid-cols-2 gap-3">
          <input type="file" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} className="col-span-2 border rounded px-3 py-2" accept=".zip,.jpg,.jpeg,.png,.tif,.tiff,.mp4,.mov,.mkv" required />
          <input placeholder="Mission Name" value={uploadForm.mission_name} onChange={(e) => setUploadForm({ ...uploadForm, mission_name: e.target.value })} className="border rounded px-3 py-2" />
          <input placeholder="Operator" value={uploadForm.operator} onChange={(e) => setUploadForm({ ...uploadForm, operator: e.target.value })} className="border rounded px-3 py-2" />
          <input type="date" value={uploadForm.flight_date} onChange={(e) => setUploadForm({ ...uploadForm, flight_date: e.target.value })} className="border rounded px-3 py-2" />
          <input type="number" step="0.1" placeholder="GSD (cm)" value={uploadForm.gsd_cm} onChange={(e) => setUploadForm({ ...uploadForm, gsd_cm: +e.target.value })} className="border rounded px-3 py-2" />
          <input type="number" placeholder="Image Count" value={uploadForm.image_count} onChange={(e) => setUploadForm({ ...uploadForm, image_count: +e.target.value })} className="border rounded px-3 py-2" />
          <input placeholder='Area BBox JSON (optional)' value={uploadForm.area_bbox} onChange={(e) => setUploadForm({ ...uploadForm, area_bbox: e.target.value })} className="border rounded px-3 py-2" />
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={uploadForm.auto_process} onChange={(e) => setUploadForm({ ...uploadForm, auto_process: e.target.checked })} />
            Auto process after upload
          </label>
          <button type="submit" disabled={uploading} className="col-span-2 bg-indigo-600 text-white py-2 rounded-lg disabled:opacity-60">
            {uploading ? 'Uploading...' : 'Upload & Run'}
          </button>
        </form>
      </div>

      <div className="bg-white border rounded-xl p-4 mb-6">
        <h3 className="font-semibold mb-3">B) Trigger by Area (BBox)</h3>
        <div className="grid md:grid-cols-2 gap-3">
          <select value={scanForm.source} onChange={(e) => setScanForm((p) => ({ ...p, source: e.target.value }))} className="border rounded px-3 py-2 text-sm">
            <option value="SENTINEL-2">Sentinel-2</option>
            <option value="LANDSAT-9">Landsat-9</option>
            <option value="LANDSAT-8">Landsat-8</option>
            <option value="OAM">OpenAerialMap</option>
          </select>
          <input value={scanForm.bbox} onChange={(e) => setScanForm((p) => ({ ...p, bbox: e.target.value }))} className="border rounded px-3 py-2 text-sm" placeholder="lon_min,lat_min,lon_max,lat_max" />
          <input type="number" min="1" max="50" value={scanForm.limit} onChange={(e) => setScanForm((p) => ({ ...p, limit: e.target.value }))} className="border rounded px-3 py-2 text-sm" placeholder="Result limit" />
          <input type="number" min="0" max="100" value={scanForm.max_cloud} onChange={(e) => setScanForm((p) => ({ ...p, max_cloud: e.target.value }))} className="border rounded px-3 py-2 text-sm" placeholder="Max cloud" />
          <input type="date" value={scanForm.date_from} onChange={(e) => setScanForm((p) => ({ ...p, date_from: e.target.value }))} className="border rounded px-3 py-2 text-sm" />
          <input type="date" value={scanForm.date_to} onChange={(e) => setScanForm((p) => ({ ...p, date_to: e.target.value }))} className="border rounded px-3 py-2 text-sm" />
          <label className="flex items-center gap-2 text-sm text-gray-700 md:col-span-2">
            <input type="checkbox" checked={scanForm.forward_to_inference} onChange={(e) => setScanForm((p) => ({ ...p, forward_to_inference: e.target.checked }))} />
            Forward to inference after fetch
          </label>
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={previewSatelliteScenes} disabled={scanLoading} className="bg-blue-600 text-white px-3 py-2 rounded text-sm disabled:opacity-60">
            {scanLoading ? 'Checking...' : 'Preview Area'}
          </button>
          <button onClick={triggerSatelliteScan} disabled={scanLoading} className="bg-primary-600 text-white px-3 py-2 rounded text-sm disabled:opacity-60">Run Area Scan</button>
        </div>
        {scenePreview && <p className="text-sm text-gray-600 mt-2">Preview returned {scenePreview.count} scene(s).</p>}
      </div>

      <div className="bg-white rounded-xl border overflow-hidden mb-6">
        <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Recent Missions</div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Mission</th>
              <th className="text-left px-4 py-3">Operator</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(missions || []).map((m) => (
              <tr key={m.id}>
                <td className="px-4 py-3">{m.mission_name}</td>
                <td className="px-4 py-3">{m.operator || '-'}</td>
                <td className="px-4 py-3">{m.processing_status}</td>
                <td className="px-4 py-3 text-xs text-gray-500">{m.created_at || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-white rounded-xl border overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Latest Detections Pending Review</div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">ID</th>
              <th className="text-left px-4 py-3">Severity</th>
              <th className="text-left px-4 py-3">Confidence</th>
              <th className="text-left px-4 py-3">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(pending || []).slice(0, 20).map((row) => (
              <tr key={row.id}>
                <td className="px-4 py-3">{row.id}</td>
                <td className="px-4 py-3">{row.severity || '-'}</td>
                <td className="px-4 py-3">{(Number(row.confidence_score || 0) * 100).toFixed(1)}%</td>
                <td className="px-4 py-3">{Number(row.risk_score || 0).toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
