import { useFetch } from '../hooks/useFetch';

export default function ModuleCompiledPipeline() {
  const { data, loading, error, refetch } = useFetch('/admin/module-demo/compiled-pipeline');

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module Demo · Compiled Pipeline</h2>
        <button onClick={refetch} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading pipeline summary...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Total Potholes</p>
              <p className="text-2xl font-bold">{data.overall?.total_potholes ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Open Complaints</p>
              <p className="text-2xl font-bold">{data.overall?.open_complaints ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Scans with Scores</p>
              <p className="text-2xl font-bold">{data.overall?.scans_with_scores ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Recent Task Runs</p>
              <p className="text-2xl font-bold">{data.overall?.recent_task_runs ?? 0}</p>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4 mb-6">
            <h3 className="font-semibold mb-3">Module Health Snapshot</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <div className="border rounded p-3">
                <p className="text-gray-500">Detection Module</p>
                <p className="font-semibold">{data.modules?.detection?.status || 'unknown'}</p>
                <p className="text-xs text-gray-500 mt-1">Recent potholes: {data.modules?.detection?.recent_potholes ?? 0}</p>
              </div>
              <div className="border rounded p-3">
                <p className="text-gray-500">Prediction Module</p>
                <p className="font-semibold">{data.modules?.prediction?.status || 'unknown'}</p>
                <p className="text-xs text-gray-500 mt-1">Recent tasks: {data.modules?.prediction?.recent_tasks ?? 0}</p>
              </div>
              <div className="border rounded p-3">
                <p className="text-gray-500">Escalation Module</p>
                <p className="font-semibold">{data.modules?.escalation?.status || 'unknown'}</p>
                <p className="text-xs text-gray-500 mt-1">Open complaints: {data.modules?.escalation?.open_complaints ?? 0}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border overflow-hidden mb-6">
            <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Recent Pipeline Events</div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3">Type</th>
                  <th className="text-left px-4 py-3">ID</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Created At</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.recent_events || []).map((e) => (
                  <tr key={`${e.type}-${e.id}`}>
                    <td className="px-4 py-3">{e.type}</td>
                    <td className="px-4 py-3">{e.id}</td>
                    <td className="px-4 py-3">{e.status || '-'}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{e.created_at || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white border rounded-xl p-4">
            <h3 className="font-semibold mb-3">Counts by Source</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              {Object.entries(data.counts_by_source || {}).map(([source, count]) => (
                <div key={source} className="border rounded p-3">
                  <p className="text-gray-500 capitalize">{source}</p>
                  <p className="font-semibold text-lg">{count}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
