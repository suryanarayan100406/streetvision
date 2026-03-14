import { useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function ModuleEscalationLogic() {
  const { data, loading, error, refetch } = useFetch('/admin/escalation/overview');
  const [runningEsc, setRunningEsc] = useState(false);
  const [runningRev, setRunningRev] = useState(false);
  const [runningSync, setRunningSync] = useState(false);

  const runEscalation = async () => {
    try {
      setRunningEsc(true);
      const { data: res } = await api.post('/admin/escalation/run-escalation');
      toast.success(`Escalation check queued (${res.task_id?.slice(0, 8) || 'task'})`);
      setTimeout(refetch, 1500);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to queue escalation check');
    } finally {
      setRunningEsc(false);
    }
  };

  const runReverify = async () => {
    try {
      setRunningRev(true);
      const { data: res } = await api.post('/admin/escalation/run-reverify');
      toast.success(`Reverify check queued (${res.task_id?.slice(0, 8) || 'task'})`);
      setTimeout(refetch, 1500);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to queue reverify check');
    } finally {
      setRunningRev(false);
    }
  };

  const runPortalSync = async () => {
    try {
      setRunningSync(true);
      const { data: res } = await api.post('/admin/escalation/run-portal-sync');
      toast.success(`Portal sync queued (${res.task_id?.slice(0, 8) || 'task'})`);
      setTimeout(refetch, 1200);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to queue portal sync');
    } finally {
      setRunningSync(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module · Escalation & Reverify</h2>
        <div className="flex items-center gap-2">
          <button onClick={runPortalSync} disabled={runningSync} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-60">
            {runningSync ? 'Queueing...' : 'Sync Detected → Portal'}
          </button>
          <button onClick={runEscalation} disabled={runningEsc} className="bg-orange-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-60">
            {runningEsc ? 'Queueing...' : 'Run Escalation Check'}
          </button>
          <button onClick={runReverify} disabled={runningRev} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-60">
            {runningRev ? 'Queueing...' : 'Run Reverify Check'}
          </button>
          <button onClick={refetch} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading live escalation data...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Open Complaints</p>
              <p className="text-2xl font-bold">{data.summary?.open_complaints ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Due Reverify</p>
              <p className="text-2xl font-bold">{data.summary?.due_reverify ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Recent Scans</p>
              <p className="text-2xl font-bold">{data.summary?.recent_scans ?? 0}</p>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4 mb-6">
            <h3 className="font-semibold mb-3">Escalation Levels</h3>
            <div className="grid grid-cols-4 gap-3 text-sm">
              {(data.escalation_levels || []).map((x) => (
                <div key={x.level} className="border rounded p-3">
                  <p className="text-gray-500">Level {x.level}</p>
                  <p className="font-semibold text-lg">{x.count}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border overflow-hidden mb-6">
            <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Recent Open Complaints</div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3">Complaint</th>
                  <th className="text-left px-4 py-3">Pothole</th>
                  <th className="text-left px-4 py-3">Portal Status</th>
                  <th className="text-left px-4 py-3">Escalation</th>
                  <th className="text-left px-4 py-3">Target</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.recent_open_complaints || []).map((c) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3">{c.id}</td>
                    <td className="px-4 py-3">{c.pothole_id}</td>
                    <td className="px-4 py-3">{c.portal_status || '-'}</td>
                    <td className="px-4 py-3">L{c.escalation_level ?? 0}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{c.escalation_target || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-xl border overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">Recent Reverify Scans</div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3">Scan</th>
                  <th className="text-left px-4 py-3">Pothole</th>
                  <th className="text-left px-4 py-3">Repair Status</th>
                  <th className="text-left px-4 py-3">SSIM</th>
                  <th className="text-left px-4 py-3">Siamese</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.recent_scans_list || []).map((s) => (
                  <tr key={s.id}>
                    <td className="px-4 py-3">{s.id}</td>
                    <td className="px-4 py-3">{s.pothole_id}</td>
                    <td className="px-4 py-3">{s.repair_status || '-'}</td>
                    <td className="px-4 py-3">{Number(s.ssim_score || 0).toFixed(4)}</td>
                    <td className="px-4 py-3">{Number(s.siamese_score || 0).toFixed(4)}</td>
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
