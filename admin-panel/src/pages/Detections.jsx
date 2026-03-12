import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';

export default function Detections() {
  const { data: pending, refetch } = useFetch('/admin/detections/pending?confidence_below=0.7&limit=50');

  const approve = async (id) => {
    await api.post(`/admin/detections/${id}/approve`);
    toast.success('Detection approved & queued for filing');
    refetch();
  };

  const reject = async (id) => {
    await api.post(`/admin/detections/${id}/reject`);
    toast.success('Detection rejected');
    refetch();
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Detection Review</h2>
      <p className="text-gray-500 text-sm mb-4">
        Potholes below confidence threshold (0.70) requiring manual review.
      </p>

      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">ID</th>
              <th className="text-left px-4 py-3">Location</th>
              <th className="text-left px-4 py-3">Highway</th>
              <th className="text-left px-4 py-3">Severity</th>
              <th className="text-left px-4 py-3">Confidence</th>
              <th className="text-left px-4 py-3">Risk</th>
              <th className="text-left px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {pending?.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">{p.id}</td>
                <td className="px-4 py-3 text-xs">{p.latitude?.toFixed(4)}, {p.longitude?.toFixed(4)}</td>
                <td className="px-4 py-3">{p.nh_number}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    p.severity === 'Critical' ? 'bg-red-100 text-red-700' :
                    p.severity === 'High' ? 'bg-orange-100 text-orange-700' :
                    p.severity === 'Medium' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-green-100 text-green-700'
                  }`}>
                    {p.severity}
                  </span>
                </td>
                <td className="px-4 py-3">{(p.confidence_score * 100).toFixed(1)}%</td>
                <td className="px-4 py-3">{p.risk_score?.toFixed(1)}</td>
                <td className="px-4 py-3 flex gap-2">
                  <button onClick={() => approve(p.id)} className="text-xs bg-green-100 hover:bg-green-200 text-green-700 px-3 py-1 rounded">
                    Approve
                  </button>
                  <button onClick={() => reject(p.id)} className="text-xs bg-red-100 hover:bg-red-200 text-red-700 px-3 py-1 rounded">
                    Reject
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {(!pending || pending.length === 0) && (
          <p className="p-6 text-center text-gray-400">No detections pending review</p>
        )}
      </div>
    </div>
  );
}
