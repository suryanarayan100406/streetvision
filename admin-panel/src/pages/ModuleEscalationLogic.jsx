import { Fragment, useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function ModuleEscalationLogic() {
  const { data, loading, error, refetch } = useFetch('/admin/escalation/overview');
  const [runningEsc, setRunningEsc] = useState(false);
  const [runningRev, setRunningRev] = useState(false);
  const [runningSync, setRunningSync] = useState(false);
  const [expandedComplaintId, setExpandedComplaintId] = useState(null);

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

  const slaBadgeClass = (status) => {
    if (status === 'OVERDUE') return 'bg-red-100 text-red-700';
    if (status === 'DUE_SOON') return 'bg-amber-100 text-amber-700';
    if (status === 'ON_TRACK') return 'bg-green-100 text-green-700';
    return 'bg-gray-100 text-gray-600';
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
          <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
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
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="text-xs text-red-700">SLA Overdue</p>
              <p className="text-2xl font-bold text-red-700">{data.summary?.sla_overdue ?? 0}</p>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-xs text-amber-700">SLA Due Soon</p>
              <p className="text-2xl font-bold text-amber-700">{data.summary?.sla_due_soon ?? 0}</p>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="text-xs text-green-700">SLA On Track</p>
              <p className="text-2xl font-bold text-green-700">{data.summary?.sla_on_track ?? 0}</p>
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
                  <th className="text-left px-4 py-3">Portal Ref</th>
                  <th className="text-left px-4 py-3">Portal Status</th>
                  <th className="text-left px-4 py-3">Escalation</th>
                  <th className="text-left px-4 py-3">Filing</th>
                  <th className="text-left px-4 py-3">Open Days</th>
                  <th className="text-left px-4 py-3">SLA</th>
                  <th className="text-left px-4 py-3">Latest Verify</th>
                  <th className="text-left px-4 py-3">Complaint Preview</th>
                  <th className="text-left px-4 py-3">Target</th>
                  <th className="text-left px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.recent_open_complaints || []).map((c) => (
                  <Fragment key={c.id}>
                    <tr key={`row-${c.id}`}>
                      <td className="px-4 py-3">{c.id}</td>
                      <td className="px-4 py-3">{c.pothole_id}</td>
                      <td className="px-4 py-3 text-xs text-gray-500">{c.portal_ref || '-'}</td>
                      <td className="px-4 py-3">{c.portal_status || '-'}</td>
                      <td className="px-4 py-3">L{c.escalation_level ?? 0}</td>
                      <td className="px-4 py-3 text-xs text-gray-500">{c.filing_method || '-'}</td>
                      <td className="px-4 py-3">{c.days_open ?? 0}</td>
                      <td className="px-4 py-3 text-xs">
                        <span className={`inline-flex rounded-full px-2 py-1 font-semibold ${slaBadgeClass(c.sla_status)}`}>
                          {c.sla_status || 'UNKNOWN'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        <div>{c.latest_verification_status || '-'}</div>
                        <div>{c.latest_verification_date || ''}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-600 max-w-xs">
                        <div className="line-clamp-3">{c.complaint_preview || '-'}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">{c.escalation_target || '-'}</td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          className="text-xs font-medium text-blue-700 hover:text-blue-900"
                          onClick={() => setExpandedComplaintId(expandedComplaintId === c.id ? null : c.id)}
                        >
                          {expandedComplaintId === c.id ? 'Hide' : 'View'}
                        </button>
                      </td>
                    </tr>

                    {expandedComplaintId === c.id && (
                      <tr key={`detail-${c.id}`} className="bg-gray-50">
                        <td colSpan={12} className="px-4 py-4">
                          <div className="grid md:grid-cols-2 gap-4 text-sm">
                            <div>
                              <p className="font-semibold mb-2">Recipient & Subject</p>
                              <div className="rounded border border-gray-200 bg-white p-3 text-gray-700 mb-3">
                                <p className="text-xs text-gray-500 mb-1">Recipient Authority</p>
                                <p className="font-medium">{c.recipient_authority || '-'}</p>
                                <p className="text-xs text-gray-500 mt-3 mb-1">Subject</p>
                                <p className="font-medium">{c.subject_line || '-'}</p>
                              </div>

                              <p className="font-semibold mb-2">SLA Timing</p>
                              <div className="rounded border border-gray-200 bg-white p-3 text-gray-700 mb-3">
                                <p className="text-xs text-gray-500 mb-1">Last Filed At</p>
                                <p className="font-medium">{c.last_filed_at || '-'}</p>
                                <p className="text-xs text-gray-500 mt-3 mb-1">Escalation Age (days)</p>
                                <p className="font-medium">{c.escalation_age_days ?? 0}</p>
                                <p className="text-xs text-gray-500 mt-3 mb-1">SLA Due At</p>
                                <p className="font-medium">{c.sla_due_at || '-'}</p>
                                <p className="text-xs text-gray-500 mt-3 mb-1">SLA Status</p>
                                <p>
                                  <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${slaBadgeClass(c.sla_status)}`}>
                                    {c.sla_status || 'UNKNOWN'}
                                  </span>
                                </p>
                                <p className="text-xs text-gray-500 mt-3 mb-1">Days To Due</p>
                                <p className="font-medium">{c.sla_days_to_due ?? 0}</p>
                                <p className="text-xs text-gray-500 mt-3 mb-1">SLA Overdue (days)</p>
                                <p className={`font-medium ${Number(c.sla_overdue_days || 0) > 0 ? 'text-red-600' : 'text-green-700'}`}>
                                  {c.sla_overdue_days ?? 0}
                                </p>
                              </div>

                              <p className="font-semibold mb-2">Filed Complaint Body</p>
                              <div className="rounded border border-gray-200 bg-white p-3 text-gray-700 whitespace-pre-wrap max-h-56 overflow-auto">
                                {c.complaint_text || 'No complaint text saved.'}
                              </div>
                            </div>
                            <div>
                              <p className="font-semibold mb-2">Filing Proof</p>
                              <div className="rounded border border-gray-200 bg-white p-3 text-gray-700">
                                <p className="mb-2 text-xs text-gray-600 break-all">{c.filing_proof_path || 'No proof path saved.'}</p>
                                {c.filing_proof_url ? (
                                  <a
                                    href={c.filing_proof_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-sm font-medium text-blue-700 hover:text-blue-900"
                                  >
                                    Open filing proof
                                  </a>
                                ) : (
                                  <p className="text-xs text-gray-500">Proof URL not available.</p>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
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
