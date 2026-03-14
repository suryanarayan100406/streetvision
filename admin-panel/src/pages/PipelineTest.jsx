import { useEffect } from 'react';
import { useFetch } from '../hooks/useFetch';

function StatusBadge({ ok }) {
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
      {ok ? 'PASS' : 'FAIL'}
    </span>
  );
}

export default function PipelineTest() {
  const reportQuery = useFetch('/admin/pipeline/full-test-report');

  useEffect(() => {
    const timer = setInterval(() => {
      reportQuery.refetch();
    }, 30000);
    return () => clearInterval(timer);
  }, [reportQuery.refetch]);

  const report = reportQuery.data;

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Pipeline Test Lab</h2>
          <p className="text-sm text-gray-500 mt-1">
            Full integration checks for model readiness, pipeline activity, queues, and recent failures.
          </p>
        </div>
        <button
          onClick={reportQuery.refetch}
          className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm"
        >
          Run Checks
        </button>
      </div>

      {reportQuery.loading && !report ? (
        <div className="bg-white rounded-xl border p-6 text-sm text-gray-500">Running pipeline checks...</div>
      ) : null}

      {reportQuery.error ? (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Could not load pipeline test report: {reportQuery.error}
        </div>
      ) : null}

      {report ? (
        <>
          <div className={`mb-6 rounded-xl border px-4 py-3 text-sm ${report.overall_status === 'healthy' ? 'border-green-200 bg-green-50 text-green-700' : 'border-yellow-200 bg-yellow-50 text-yellow-700'}`}>
            Overall status: <span className="font-semibold">{report.overall_status?.toUpperCase()}</span>
            <span className="ml-3 text-xs">Generated: {report.generated_at ? new Date(report.generated_at).toLocaleString() : 'N/A'}</span>
          </div>

          <h3 className="text-lg font-semibold mb-3">Validation Checks</h3>
          <div className="bg-white rounded-xl border divide-y mb-8">
            {(report.checks || []).map((check) => (
              <div key={check.name} className="px-4 py-3 flex items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-800">{check.name}</p>
                  <p className="text-xs text-gray-500 mt-1 break-all">{check.detail}</p>
                </div>
                <StatusBadge ok={!!check.ok} />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div className="bg-white rounded-xl border p-4">
              <h4 className="font-semibold mb-2">Model</h4>
              <p className="text-sm text-gray-700">Path: <span className="font-mono text-xs break-all">{report.model?.path || 'N/A'}</span></p>
              <p className="text-sm text-gray-700 mt-1">Exists: {String(report.model?.exists)}</p>
              <p className="text-sm text-gray-700 mt-1">Size: {report.model?.size_mb || 0} MB</p>
              <p className="text-sm text-gray-700 mt-1">SHA256: <span className="font-mono text-xs">{report.model?.sha256_prefix || 'N/A'}</span></p>
            </div>

            <div className="bg-white rounded-xl border p-4">
              <h4 className="font-semibold mb-2">24h Activity</h4>
              <p className="text-sm text-gray-700">Source reports: {report.activity_24h?.source_reports ?? 0}</p>
              <p className="text-sm text-gray-700 mt-1">Potholes detected: {report.activity_24h?.potholes_detected ?? 0}</p>
              <p className="text-sm text-gray-700 mt-1">Tasks success: {report.activity_24h?.tasks_success ?? 0}</p>
              <p className="text-sm text-gray-700 mt-1">Tasks failed: {report.activity_24h?.tasks_failed ?? 0}</p>
            </div>

            <div className="bg-white rounded-xl border p-4">
              <h4 className="font-semibold mb-2">Queue Depths</h4>
              {Object.keys(report.queues || {}).length ? (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(report.queues).map(([name, depth]) => (
                    <div key={name} className="rounded bg-gray-50 px-2 py-1 text-sm flex items-center justify-between">
                      <span className="text-gray-600">{name}</span>
                      <span className="font-semibold">{depth}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">Queue metrics unavailable.</p>
              )}
            </div>
          </div>

          <h3 className="text-lg font-semibold mb-3">Recent Failed Tasks</h3>
          <div className="bg-white rounded-xl border max-h-80 overflow-y-auto">
            {!report.recent_failed_tasks?.length ? (
              <p className="p-4 text-sm text-gray-500">No recent failed tasks.</p>
            ) : (
              <div className="divide-y">
                {report.recent_failed_tasks.map((task) => (
                  <div key={task.id} className="p-4">
                    <p className="font-medium text-gray-800">{task.task_name || 'Unknown task'}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {task.completed_at ? new Date(task.completed_at).toLocaleString() : 'No completion time'}
                      {task.duration_seconds ? ` • ${Number(task.duration_seconds).toFixed(2)}s` : ''}
                    </p>
                    {task.result ? (
                      <pre className="mt-2 text-xs bg-gray-50 border rounded p-2 overflow-x-auto">{JSON.stringify(task.result, null, 2)}</pre>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
