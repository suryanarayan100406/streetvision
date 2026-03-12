import { useFetch } from '../hooks/useFetch';

export default function Logs() {
  const { data: auditLogs } = useFetch('/admin/logs/audit?limit=50');
  const { data: geminiUsage } = useFetch('/admin/logs/gemini/usage');
  const { data: geminiLogs } = useFetch('/admin/logs/gemini?limit=20');

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Logs & Audit</h2>

      {/* Gemini usage */}
      <h3 className="text-lg font-semibold mb-3">Gemini API Usage (7 days)</h3>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-8">
        <div className="bg-white rounded-lg border p-3 text-center">
          <p className="text-2xl font-bold">{geminiUsage?.total_calls || 0}</p>
          <p className="text-xs text-gray-500">API Calls</p>
        </div>
        <div className="bg-white rounded-lg border p-3 text-center">
          <p className="text-2xl font-bold">{geminiUsage?.total_input_tokens || 0}</p>
          <p className="text-xs text-gray-500">Input Tokens</p>
        </div>
        <div className="bg-white rounded-lg border p-3 text-center">
          <p className="text-2xl font-bold">{geminiUsage?.total_output_tokens || 0}</p>
          <p className="text-xs text-gray-500">Output Tokens</p>
        </div>
        <div className="bg-white rounded-lg border p-3 text-center">
          <p className="text-2xl font-bold">{geminiUsage?.avg_latency_ms || 0}ms</p>
          <p className="text-xs text-gray-500">Avg Latency</p>
        </div>
        <div className="bg-white rounded-lg border p-3 text-center">
          <p className="text-2xl font-bold text-red-600">{geminiUsage?.failures || 0}</p>
          <p className="text-xs text-gray-500">Failures</p>
        </div>
      </div>

      {/* Audit trail */}
      <h3 className="text-lg font-semibold mb-3">Admin Audit Trail</h3>
      <div className="bg-white rounded-xl border overflow-hidden mb-8">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Action</th>
              <th className="text-left px-4 py-3">Entity</th>
              <th className="text-left px-4 py-3">Entity ID</th>
              <th className="text-left px-4 py-3">Admin</th>
              <th className="text-left px-4 py-3">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {auditLogs?.map((l) => (
              <tr key={l.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{l.action}</td>
                <td className="px-4 py-3">{l.entity_type}</td>
                <td className="px-4 py-3">{l.entity_id}</td>
                <td className="px-4 py-3">{l.admin_id}</td>
                <td className="px-4 py-3 text-gray-500">{l.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent Gemini calls */}
      <h3 className="text-lg font-semibold mb-3">Recent Gemini Calls</h3>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Pothole</th>
              <th className="text-left px-4 py-3">Model</th>
              <th className="text-left px-4 py-3">Tokens (in/out)</th>
              <th className="text-left px-4 py-3">Latency</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {geminiLogs?.map((g) => (
              <tr key={g.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">{g.pothole_id}</td>
                <td className="px-4 py-3">{g.model_used}</td>
                <td className="px-4 py-3">{g.input_tokens}/{g.output_tokens}</td>
                <td className="px-4 py-3">{g.latency_ms}ms</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs ${g.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {g.success ? 'OK' : 'Failed'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
