import { useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function ModuleVerificationRecheck() {
  const { data, loading, error, refetch } = useFetch('/admin/verification/overview');
  const [running, setRunning] = useState(false);

  const runVerification = async () => {
    try {
      setRunning(true);
      const { data: res } = await api.post('/admin/verification/run');
      toast.success(`Verification queued (${res.task_id?.slice(0, 8) || 'task'})`);
      setTimeout(refetch, 1500);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to queue verification');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module · 14-Day Verification Recheck</h2>
        <div className="flex items-center gap-2">
          <button onClick={runVerification} disabled={running} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-60">
            {running ? 'Queueing...' : 'Run Reverification'}
          </button>
          <button onClick={refetch} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading verification module...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Due Reverification</p>
              <p className="text-2xl font-bold">{data.summary?.due_reverification ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Resolved Complaints</p>
              <p className="text-2xl font-bold">{data.summary?.resolved_complaints ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Unresolved / Escalated</p>
              <p className="text-2xl font-bold">{data.summary?.unresolved_or_escalated ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Recent Reverify Scans</p>
              <p className="text-2xl font-bold">{data.summary?.recent_reverify_scans ?? 0}</p>
            </div>
          </div>

          <div className="bg-white rounded-xl border overflow-hidden mb-6">
            <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Cases Due for 14-Day Verification</div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3">Complaint</th>
                  <th className="text-left px-4 py-3">Pothole</th>
                  <th className="text-left px-4 py-3">Portal Status</th>
                  <th className="text-left px-4 py-3">Escalation</th>
                  <th className="text-left px-4 py-3">Filed / Escalated</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.due_cases || []).map((c) => (
                  <tr key={`${c.complaint_id}-${c.pothole_id}`}>
                    <td className="px-4 py-3">{c.complaint_id}</td>
                    <td className="px-4 py-3">{c.pothole_id}</td>
                    <td className="px-4 py-3">{c.portal_status || '-'}</td>
                    <td className="px-4 py-3">L{c.escalation_level ?? 0}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{c.escalated_at || c.filed_at || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-xl border overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Recent Reverification Scans</div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3">Scan</th>
                  <th className="text-left px-4 py-3">Pothole</th>
                  <th className="text-left px-4 py-3">Repair Status</th>
                  <th className="text-left px-4 py-3">SSIM</th>
                  <th className="text-left px-4 py-3">Siamese</th>
                  <th className="text-left px-4 py-3">Complaint Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.recent_scans || []).map((s) => (
                  <tr key={s.scan_id}>
                    <td className="px-4 py-3">{s.scan_id}</td>
                    <td className="px-4 py-3">{s.pothole_id}</td>
                    <td className="px-4 py-3">{s.repair_status || '-'}</td>
                    <td className="px-4 py-3">{Number(s.ssim_score || 0).toFixed(4)}</td>
                    <td className="px-4 py-3">{Number(s.siamese_score || 0).toFixed(4)}</td>
                    <td className="px-4 py-3">{s.portal_status || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
