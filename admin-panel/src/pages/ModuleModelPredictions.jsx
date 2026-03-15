import { useMemo, useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';
import GooglePotholeMap from '../components/GooglePotholeMap';

const SIMULATED_PREDICTION_HINTS = [
  {
    id: 'sim-nh53-01',
    highway: 'NH-53',
    district: 'Raipur',
    latitude: 21.2522,
    longitude: 81.6314,
    probability: 0.41,
    note: 'Possible pothole-prone patch after rain; low-confidence model hint.',
  },
  {
    id: 'sim-nh53-02',
    highway: 'NH-53',
    district: 'Raipur',
    latitude: 21.2287,
    longitude: 81.7079,
    probability: 0.38,
    note: 'Surface undulation likely; requires field validation.',
  },
  {
    id: 'sim-nh53-03',
    highway: 'NH-53',
    district: 'Mahasamund',
    latitude: 21.1669,
    longitude: 81.9021,
    probability: 0.44,
    note: 'Historic stress zone; model predicts possible future pothole.',
  },
  {
    id: 'sim-nh53-04',
    highway: 'NH-53',
    district: 'Mahasamund',
    latitude: 21.1243,
    longitude: 82.0356,
    probability: 0.36,
    note: 'Possible defect area; currently below detection threshold.',
  },
  {
    id: 'sim-nh53-05',
    highway: 'NH-53',
    district: 'Mahasamund',
    latitude: 21.1086,
    longitude: 82.0993,
    probability: 0.4,
    note: 'Model-only advisory point, not a confirmed pothole.',
  },
];

export default function ModuleModelPredictions() {
  const { data: models, loading, error, refetch } = useFetch('/admin/models/');
  const { data: taskFeed, refetch: refetchTaskFeed } = useFetch('/admin/pipeline/task-history?task_name=run_inference_on_tile&limit=20');
  const { data: liveGeojson } = useFetch('/public/geojson');

  const [bootstrapTaskId, setBootstrapTaskId] = useState('');
  const [bootstrapState, setBootstrapState] = useState(null);
  const [runningBootstrap, setRunningBootstrap] = useState(false);
  const [checkingBootstrap, setCheckingBootstrap] = useState(false);
  const [showSimulatedHints, setShowSimulatedHints] = useState(true);

  const simulatedFeatures = useMemo(
    () => SIMULATED_PREDICTION_HINTS.map((hint) => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [hint.longitude, hint.latitude],
      },
      properties: {
        id: hint.id,
        severity: 'Simulated',
        risk_score: Math.round(hint.probability * 100),
        status: 'SIMULATED_HINT',
        nh_number: hint.highway,
        district: hint.district,
        detected_at: null,
        simulated: true,
        note: hint.note,
      },
    })),
    []
  );

  const predictionMapGeojson = useMemo(() => {
    const liveFeatures = Array.isArray(liveGeojson?.features) ? liveGeojson.features : [];
    return {
      type: 'FeatureCollection',
      features: showSimulatedHints ? [...liveFeatures, ...simulatedFeatures] : liveFeatures,
    };
  }, [liveGeojson, showSimulatedHints, simulatedFeatures]);

  const activeByType = (models || []).reduce((acc, model) => {
    if (model.is_active) acc[model.model_type] = model.model_name;
    return acc;
  }, {});

  const runBootstrap = async () => {
    try {
      setRunningBootstrap(true);
      const { data } = await api.post('/admin/models/bootstrap');
      setBootstrapTaskId(data.task_id || '');
      toast.success('Model bootstrap task queued');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to queue bootstrap');
    } finally {
      setRunningBootstrap(false);
    }
  };

  const checkBootstrap = async () => {
    if (!bootstrapTaskId) {
      toast.error('No task id available yet');
      return;
    }
    try {
      setCheckingBootstrap(true);
      const { data } = await api.get(`/admin/models/bootstrap/${bootstrapTaskId}`);
      setBootstrapState(data);
      if (data.state === 'SUCCESS') {
        toast.success('Bootstrap completed');
        refetch();
      } else if (data.state === 'FAILURE') {
        toast.error('Bootstrap failed');
      } else {
        toast('Bootstrap still running');
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to check bootstrap status');
    } finally {
      setCheckingBootstrap(false);
    }
  };

  const activateModel = async (id) => {
    try {
      await api.post(`/admin/models/${id}/activate`);
      toast.success(`Model ${id} activated`);
      refetch();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Activation failed');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module · Model Predictions</h2>
        <button onClick={() => { refetch(); refetchTaskFeed(); }} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading models...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="bg-white border rounded-xl p-4 mb-6">
        <h3 className="font-semibold mb-3">A) Bootstrap Prediction Stack</h3>
        <p className="text-sm text-gray-600 mb-3">Runs backend warmup for YOLO, MiDaS and Siamese models.</p>
        <div className="flex gap-2 mb-3">
          <button onClick={runBootstrap} disabled={runningBootstrap} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-60">
            {runningBootstrap ? 'Queueing...' : 'Run Bootstrap'}
          </button>
          <button onClick={checkBootstrap} disabled={checkingBootstrap || !bootstrapTaskId} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-60">
            {checkingBootstrap ? 'Checking...' : 'Check Bootstrap Status'}
          </button>
        </div>
        {bootstrapTaskId && <p className="text-xs text-gray-500">Task: {bootstrapTaskId}</p>}
        {bootstrapState && <p className="text-xs text-gray-700 mt-1">State: {bootstrapState.state}</p>}
      </div>

      <div className="bg-white border rounded-xl p-4 mb-6">
        <h3 className="font-semibold mb-3">B) Active Models by Type</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          {['DETECTION', 'DEPTH', 'VERIFICATION'].map((type) => (
            <div key={type} className="border rounded p-3">
              <p className="text-gray-500">{type}</p>
              <p className="font-semibold">{activeByType[type] || 'No active model'}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-xl border overflow-hidden mb-6">
        <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Model Registry (Activate One)</div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-left px-4 py-3">Version</th>
              <th className="text-left px-4 py-3">Active</th>
              <th className="text-left px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(models || []).map((m) => (
              <tr key={m.id}>
                <td className="px-4 py-3">{m.model_name}</td>
                <td className="px-4 py-3">{m.model_type}</td>
                <td className="px-4 py-3">{m.version}</td>
                <td className="px-4 py-3">{m.is_active ? 'Yes' : 'No'}</td>
                <td className="px-4 py-3">
                  <button onClick={() => activateModel(m.id)} disabled={m.is_active} className="text-xs bg-primary-100 text-primary-700 px-3 py-1 rounded disabled:opacity-50">
                    Activate
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-white rounded-xl border overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Recent Inference Tasks</div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Task</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Duration</th>
              <th className="text-left px-4 py-3">Completed</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(taskFeed || []).map((t) => (
              <tr key={t.id}>
                <td className="px-4 py-3 text-xs">{t.task_id}</td>
                <td className="px-4 py-3">{t.status}</td>
                <td className="px-4 py-3">{Number(t.duration_seconds || 0).toFixed(2)}s</td>
                <td className="px-4 py-3 text-xs text-gray-500">{t.completed_at || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-amber-50 rounded-xl border border-amber-200 overflow-hidden mt-6">
        <div className="px-4 py-3 border-b border-amber-200 bg-amber-100 font-semibold text-sm flex items-center justify-between">
          <span>C) Simulated Prediction Hints (Not Accurate)</span>
          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-amber-900 inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={showSimulatedHints}
                onChange={(e) => setShowSimulatedHints(e.target.checked)}
              />
              Show simulated hints
            </label>
            <span className="text-xs font-bold text-amber-800">FAKE / MODEL-ONLY</span>
          </div>
        </div>
        <div className="px-4 py-3 text-xs text-amber-900 bg-amber-50 border-b border-amber-200">
          These are intentionally synthetic low-confidence hints to show where potholes might appear. They are not confirmed detections and must be field-verified.
        </div>

        <div className="p-4 border-b border-amber-200 bg-white">
          <div className="h-80 overflow-hidden rounded-lg border border-amber-200">
            <GooglePotholeMap
              geojson={predictionMapGeojson}
              heightClassName="h-full w-full"
              popupLinkPrefix="/admin"
            />
          </div>
          <div className="mt-3 text-xs text-gray-700 flex items-center gap-4">
            <span className="inline-flex items-center gap-2"><span className="inline-block w-3 h-3 rounded-full bg-purple-600" /> Simulated hints</span>
            <span className="inline-flex items-center gap-2"><span className="inline-block w-3 h-3 rounded-full bg-red-600" /> Real critical</span>
            <span className="inline-flex items-center gap-2"><span className="inline-block w-3 h-3 rounded-full bg-green-600" /> Real low</span>
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-amber-100 border-b border-amber-200">
            <tr>
              <th className="text-left px-4 py-3">Highway</th>
              <th className="text-left px-4 py-3">District</th>
              <th className="text-left px-4 py-3">Coordinates</th>
              <th className="text-left px-4 py-3">Probability</th>
              <th className="text-left px-4 py-3">Comment</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-amber-100">
            {SIMULATED_PREDICTION_HINTS.map((hint) => (
              <tr key={hint.id}>
                <td className="px-4 py-3">{hint.highway}</td>
                <td className="px-4 py-3">{hint.district}</td>
                <td className="px-4 py-3 text-xs text-gray-700">
                  {hint.latitude.toFixed(6)}, {hint.longitude.toFixed(6)}
                </td>
                <td className="px-4 py-3">{(hint.probability * 100).toFixed(0)}%</td>
                <td className="px-4 py-3 text-xs text-gray-700">{hint.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
