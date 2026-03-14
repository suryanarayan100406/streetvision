import { Fragment, useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function Satellites() {
  const { data: sources, refetch: refetchSources } = useFetch('/admin/satellites/sources');
  const { data: jobs, refetch: refetchJobs } = useFetch('/admin/satellites/jobs?limit=20');
  const { data: credentialsStatus } = useFetch('/admin/satellites/credentials-status');
  const { data: downloadLogs, refetch: refetchDownloadLogs } = useFetch('/admin/satellites/download-logs?limit=12');
  const [editingSourceId, setEditingSourceId] = useState(null);
  const [credentialsDrafts, setCredentialsDrafts] = useState({});
  const [savingSourceId, setSavingSourceId] = useState(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [scenePreview, setScenePreview] = useState(null);
  const [scanForm, setScanForm] = useState({
    source: 'SENTINEL-2',
    bbox: '',
    limit: 12,
    max_cloud: 20,
    date_from: '',
    date_to: '',
    forward_to_inference: true,
  });

  const toggleSource = async (id, enabled) => {
    await api.patch(`/admin/satellites/sources/${id}`, { enabled: !enabled });
    toast.success(`Source ${!enabled ? 'enabled' : 'disabled'}`);
    refetchSources();
  };

  const testConnection = async (id) => {
    try {
      const { data } = await api.post(`/admin/satellites/sources/${id}/test`);
      if (data.success) {
        toast.success('Connection successful');
      } else {
        toast.error(data.error || 'Connection test failed');
      }
    } catch {
      toast.error('Connection test failed');
    }
  };

  const triggerIngestion = async (name) => {
    const { data } = await api.post(`/admin/satellites/trigger/${name}`);
    toast.success(`Triggered job ${data.job_id}`);
    refetchJobs();
  };

  const openCredentialsEditor = (source) => {
    setEditingSourceId(source.id);
    setCredentialsDrafts((prev) => ({
      ...prev,
      [source.id]: JSON.stringify(source.credentials || {}, null, 2),
    }));
  };

  const saveCredentials = async (sourceId) => {
    const raw = credentialsDrafts[sourceId] || '{}';
    let parsed;
    try {
      parsed = JSON.parse(raw);
      if (Array.isArray(parsed) || typeof parsed !== 'object' || parsed === null) {
        throw new Error('Credentials must be a JSON object');
      }
    } catch {
      toast.error('Invalid JSON. Please provide a JSON object.');
      return;
    }

    try {
      setSavingSourceId(sourceId);
      await api.patch(`/admin/satellites/sources/${sourceId}`, { credentials: parsed });
      toast.success('Credentials saved');
      await refetchSources();
    } catch {
      toast.error('Failed to save credentials');
    } finally {
      setSavingSourceId(null);
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

  const triggerCustomScan = async () => {
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
      toast.success(`Queued job ${data.job_id}`);
      refetchJobs();
      refetchDownloadLogs();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to trigger custom scan');
    } finally {
      setScanLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Satellite Sources</h2>

      <div className="bg-white rounded-xl border overflow-hidden mb-8">
        <div className="px-4 py-3 border-b bg-gray-50">
          <h3 className="text-lg font-semibold">Credentials Status</h3>
          <p className="text-xs text-gray-600">Shows which env keys are still missing for each satellite source.</p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Source</th>
              <th className="text-left px-4 py-3">Required Keys</th>
              <th className="text-left px-4 py-3">Missing Keys</th>
              <th className="text-left px-4 py-3">Ready</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {credentialsStatus?.items?.map((item) => (
              <tr key={item.source} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{item.source}</td>
                <td className="px-4 py-3 text-xs text-gray-700">{item.keys_required.length ? item.keys_required.join(', ') : 'None'}</td>
                <td className="px-4 py-3 text-xs text-gray-700">{item.keys_missing.length ? item.keys_missing.join(', ') : 'None'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${item.configured ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                    {item.configured ? 'Ready' : 'Missing'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-white rounded-xl border p-4 mb-8">
        <h3 className="text-lg font-semibold mb-3">Custom Satellite Scan</h3>
        <p className="text-xs text-gray-600 mb-3">
          Preview scenes for a bbox, then trigger a fetch that stores imagery in object storage and forwards it to inference.
        </p>
        <p className="text-xs text-amber-700 mb-3">
          Sentinel/Landsat imagery is used for corridor monitoring; pothole inference is auto-skipped for coarse resolution tiles.
        </p>
        <div className="grid md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Source</label>
            <select
              value={scanForm.source}
              onChange={(e) => setScanForm((p) => ({ ...p, source: e.target.value }))}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              <option value="SENTINEL-2">Sentinel-2</option>
              <option value="LANDSAT-9">Landsat-9</option>
              <option value="LANDSAT-8">Landsat-8</option>
              <option value="OAM">OpenAerialMap</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">BBox (lon_min,lat_min,lon_max,lat_max)</label>
            <input
              value={scanForm.bbox}
              onChange={(e) => setScanForm((p) => ({ ...p, bbox: e.target.value }))}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Result Limit</label>
            <input
              type="number"
              min="1"
              max="50"
              value={scanForm.limit}
              onChange={(e) => setScanForm((p) => ({ ...p, limit: e.target.value }))}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">From Date</label>
            <input
              type="date"
              value={scanForm.date_from}
              onChange={(e) => setScanForm((p) => ({ ...p, date_from: e.target.value }))}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">To Date</label>
            <input
              type="date"
              value={scanForm.date_to}
              onChange={(e) => setScanForm((p) => ({ ...p, date_to: e.target.value }))}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Max Cloud % (Sentinel only)</label>
            <input
              type="number"
              min="0"
              max="100"
              value={scanForm.max_cloud}
              onChange={(e) => setScanForm((p) => ({ ...p, max_cloud: e.target.value }))}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 mt-6">
            <input
              type="checkbox"
              checked={scanForm.forward_to_inference}
              onChange={(e) => setScanForm((p) => ({ ...p, forward_to_inference: e.target.checked }))}
            />
            Forward fetched imagery to inference
          </label>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={previewSatelliteScenes}
            disabled={scanLoading}
            className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded disabled:opacity-50"
          >
            {scanLoading ? 'Checking...' : 'Preview Scenes'}
          </button>
          <button
            onClick={triggerCustomScan}
            disabled={scanLoading}
            className="text-sm bg-primary-600 hover:bg-primary-700 text-white px-3 py-2 rounded disabled:opacity-50"
          >
            Trigger Full Pipeline
          </button>
        </div>

        {scenePreview && (
          <div className="mt-3 text-sm">
            <p className="font-medium">Available scenes: {scenePreview.count}</p>
            {scenePreview.items?.length > 0 && (
              <div className="grid md:grid-cols-3 gap-3 mt-3">
                {scenePreview.items.map((sample) => (
                  <div key={sample.product_id} className="border rounded-lg overflow-hidden bg-white">
                    {sample.preview_url ? (
                      <img src={sample.preview_url} alt={sample.title || sample.product_id} className="w-full h-32 object-cover bg-gray-100" />
                    ) : (
                      <div className="w-full h-32 bg-gray-100 flex items-center justify-center text-xs text-gray-500">No preview</div>
                    )}
                    <div className="p-2 text-xs">
                      <div className="font-medium break-all">{sample.title || sample.product_id}</div>
                      <div className="text-gray-600 mt-1">{sample.captured_at || 'Unknown capture time'}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <h3 className="text-lg font-semibold mb-3">Fetched Scenes</h3>
      <div className="bg-white rounded-xl border overflow-hidden mb-8">
        <div className="grid md:grid-cols-3 gap-4 p-4">
          {downloadLogs?.map((item) => (
            <div key={item.id} className="border rounded-lg overflow-hidden bg-white">
              {item.preview_url ? (
                <img src={item.preview_url} alt={item.product_id || 'satellite scene'} className="w-full h-36 object-cover bg-gray-100" />
              ) : (
                <div className="w-full h-36 bg-gray-100 flex items-center justify-center text-xs text-gray-500">No stored preview</div>
              )}
              <div className="p-3 text-xs">
                <div className="font-semibold">{item.source_name || 'Unknown source'}</div>
                <div className="break-all text-gray-700 mt-1">{item.product_id}</div>
                <div className="text-gray-500 mt-1">{item.file_size_mb ? `${item.file_size_mb} MB` : 'size n/a'}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

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
              <Fragment key={s.id}>
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
                  <td className="px-4 py-3 flex gap-2 flex-wrap">
                    <button onClick={() => toggleSource(s.id, s.enabled)} className="text-xs bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded">
                      {s.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button onClick={() => testConnection(s.id)} className="text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 px-2 py-1 rounded">
                      Test
                    </button>
                    <button onClick={() => triggerIngestion(s.name)} className="text-xs bg-primary-100 hover:bg-primary-200 text-primary-700 px-2 py-1 rounded">
                      Trigger
                    </button>
                    <button
                      onClick={() => (editingSourceId === s.id ? setEditingSourceId(null) : openCredentialsEditor(s))}
                      className="text-xs bg-purple-100 hover:bg-purple-200 text-purple-700 px-2 py-1 rounded"
                    >
                      {editingSourceId === s.id ? 'Close Credentials' : 'Edit Credentials'}
                    </button>
                  </td>
                </tr>
                {editingSourceId === s.id && (
                  <tr key={`${s.id}-editor`} className="bg-gray-50">
                    <td className="px-4 py-3" colSpan={6}>
                      <p className="text-xs text-gray-600 mb-2">
                        Enter JSON credentials for {s.name} (example: {'{"username":"...","password":"..."}'}).
                      </p>
                      <textarea
                        value={credentialsDrafts[s.id] ?? '{}'}
                        onChange={(e) =>
                          setCredentialsDrafts((prev) => ({
                            ...prev,
                            [s.id]: e.target.value,
                          }))
                        }
                        rows={6}
                        className="w-full border rounded-lg p-2 font-mono text-xs bg-white"
                      />
                      <div className="mt-2 flex gap-2">
                        <button
                          onClick={() => saveCredentials(s.id)}
                          disabled={savingSourceId === s.id}
                          className="text-xs bg-primary-600 hover:bg-primary-700 text-white px-3 py-1.5 rounded disabled:opacity-50"
                        >
                          {savingSourceId === s.id ? 'Saving...' : 'Save Credentials'}
                        </button>
                        <button
                          onClick={() =>
                            setCredentialsDrafts((prev) => ({
                              ...prev,
                              [s.id]: '{}',
                            }))
                          }
                          className="text-xs bg-gray-200 hover:bg-gray-300 px-3 py-1.5 rounded"
                        >
                          Clear
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
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
              <th className="text-left px-4 py-3">Mode</th>
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
                <td className="px-4 py-3 text-xs">
                  {j.monitoring_only_tiles > 0 && j.tiles_forwarded_to_inference === 0 ? (
                    <span className="px-2 py-1 rounded bg-amber-100 text-amber-800 font-medium">
                      Monitoring only ({j.monitoring_only_tiles})
                    </span>
                  ) : (
                    <span className="px-2 py-1 rounded bg-blue-100 text-blue-800 font-medium">
                      Inference ({j.tiles_forwarded_to_inference || 0})
                    </span>
                  )}
                </td>
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
