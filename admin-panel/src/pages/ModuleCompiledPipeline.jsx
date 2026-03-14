import { useFetch } from '../hooks/useFetch';

function StatusPill({ ok }) {
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
      {ok ? 'PASS' : 'FAIL'}
    </span>
  );
}

export default function ModuleCompiledPipeline() {
  const { data, loading, error, refetch } = useFetch('/admin/pipeline/full-test-report');

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module · Compiled Pipeline Check</h2>
        <button onClick={refetch} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Run Checks</button>
      </div>

      {loading && <p className="text-sm text-gray-500">Running real pipeline checks...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <>
          <div className={`mb-6 rounded-xl border px-4 py-3 text-sm ${data.overall_status === 'healthy' ? 'border-green-200 bg-green-50 text-green-700' : 'border-yellow-200 bg-yellow-50 text-yellow-700'}`}>
            Overall status: <span className="font-semibold">{data.overall_status?.toUpperCase()}</span>
            <span className="ml-3 text-xs">Generated: {data.generated_at ? new Date(data.generated_at).toLocaleString() : 'N/A'}</span>
          </div>

          <div className="bg-white rounded-xl border divide-y mb-6">
            {(data.checks || []).map((check) => (
              <div key={check.name} className="px-4 py-3 flex items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-800">{check.name}</p>
                  <p className="text-xs text-gray-500 mt-1 break-all">{check.detail}</p>
                </div>
                <StatusPill ok={!!check.ok} />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border p-4">
              <h3 className="font-semibold mb-2">24h Activity</h3>
              <p className="text-sm">Source reports: {data.activity_24h?.source_reports ?? 0}</p>
              <p className="text-sm">Potholes detected: {data.activity_24h?.potholes_detected ?? 0}</p>
              <p className="text-sm">Task success: {data.activity_24h?.tasks_success ?? 0}</p>
              <p className="text-sm">Task failed: {data.activity_24h?.tasks_failed ?? 0}</p>
            </div>

            <div className="bg-white rounded-xl border p-4">
              <h3 className="font-semibold mb-2">Queue Depths</h3>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {Object.entries(data.queues || {}).map(([name, depth]) => (
                  <div key={name} className="rounded bg-gray-50 px-2 py-1 flex items-center justify-between">
                    <span>{name}</span>
                    <span className="font-semibold">{depth}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
