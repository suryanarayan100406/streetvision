import { useFetch } from '../hooks/useFetch';

export default function ModuleModelPredictions() {
  const { data, loading, error, refetch } = useFetch('/admin/module-demo/model-predictions');

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module Demo · Model Predictions</h2>
        <button onClick={refetch} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading model module data...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Inference Tasks (24h)</p>
              <p className="text-2xl font-bold">{data.summary?.inference_tasks_last_24h ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Inference Success</p>
              <p className="text-2xl font-bold text-green-700">{data.summary?.inference_success ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Inference Failed</p>
              <p className="text-2xl font-bold text-red-700">{data.summary?.inference_failed ?? 0}</p>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4 mb-6">
            <h3 className="font-semibold mb-3">Active Models</h3>
            <div className="space-y-3">
              {(data.active_models || []).map((m) => (
                <div key={m.id} className="border rounded p-3 text-sm">
                  <p className="font-semibold">{m.model_name} <span className="text-gray-500">({m.version})</span></p>
                  <p className="text-gray-600">Type: {m.model_type}</p>
                  <p className="text-gray-600">mAP50: {Number(m.map50 || 0).toFixed(3)} · F1: {Number(m.f1_score || 0).toFixed(3)}</p>
                  <p className="text-xs text-gray-500 truncate">{m.weights_path || '-'}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3">Task ID</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Duration (s)</th>
                  <th className="text-left px-4 py-3">Completed</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.recent_inference_tasks || []).map((t, idx) => (
                  <tr key={`${t.task_id}-${idx}`}>
                    <td className="px-4 py-3 text-xs">{t.task_id}</td>
                    <td className="px-4 py-3">{t.status}</td>
                    <td className="px-4 py-3">{Number(t.duration_seconds || 0).toFixed(2)}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{t.completed_at || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(!data.recent_inference_tasks || data.recent_inference_tasks.length === 0) && (
              <p className="p-6 text-center text-gray-400">No recent inference tasks</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
