import { useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function ModuleModelPredictions() {
  const { data: models, loading, error, refetch } = useFetch('/admin/models/');
  const { data: taskFeed, refetch: refetchTaskFeed } = useFetch('/admin/pipeline/task-history?task_name=run_inference_on_tile&limit=20');

  const [bootstrapTaskId, setBootstrapTaskId] = useState('');
  const [bootstrapState, setBootstrapState] = useState(null);
  const [runningBootstrap, setRunningBootstrap] = useState(false);
  const [checkingBootstrap, setCheckingBootstrap] = useState(false);

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
    </div>
  );
}
