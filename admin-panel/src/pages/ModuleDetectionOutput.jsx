import { useFetch } from '../hooks/useFetch';

export default function ModuleDetectionOutput() {
  const { data, loading, error, refetch } = useFetch('/admin/module-demo/detection-output');

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module Demo · Detection Output</h2>
        <button onClick={refetch} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading detection module data...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Potholes (24h)</p>
              <p className="text-2xl font-bold">{data.summary?.potholes_last_24h ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Source Reports (24h)</p>
              <p className="text-2xl font-bold">{data.summary?.source_reports_last_24h ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Total Potholes</p>
              <p className="text-2xl font-bold">{data.summary?.total_potholes ?? 0}</p>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4 mb-6">
            <h3 className="font-semibold mb-3">By Source</h3>
            <div className="grid grid-cols-3 gap-3 text-sm">
              {(data.by_source || []).map((item) => (
                <div key={item.source} className="border rounded p-3">
                  <p className="text-gray-500">{item.source}</p>
                  <p className="font-semibold text-lg">{item.count}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3">ID</th>
                  <th className="text-left px-4 py-3">Severity</th>
                  <th className="text-left px-4 py-3">Confidence</th>
                  <th className="text-left px-4 py-3">Risk</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Image</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.recent_potholes || []).map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3">{row.id}</td>
                    <td className="px-4 py-3">{row.severity || '-'}</td>
                    <td className="px-4 py-3">{(Number(row.confidence || 0) * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3">{Number(row.risk_score || 0).toFixed(1)}</td>
                    <td className="px-4 py-3">{row.status || '-'}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 max-w-[320px] truncate">{row.image_path || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(!data.recent_potholes || data.recent_potholes.length === 0) && (
              <p className="p-6 text-center text-gray-400">No recent potholes</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
