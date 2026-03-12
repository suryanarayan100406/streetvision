import { useState } from 'react';
import useFetch from '../hooks/useFetch';

const STATUSES = ['new', 'investigating', 'in_repair', 'resolved', 'failed'];
const STATUS_COLORS = {
  new: 'bg-blue-100 text-blue-700',
  investigating: 'bg-yellow-100 text-yellow-700',
  in_repair: 'bg-purple-100 text-purple-700',
  resolved: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

export default function Kanban() {
  const { data: complaints } = useFetch('/api/dashboard/complaint-funnel');
  const [potholes, setPotholes] = useState({});

  if (!complaints) return <div className="text-center py-8">Loading...</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Complaint Resolution Pipeline</h2>
      <div className="grid lg:grid-cols-5 gap-4">
        {STATUSES.map((status) => (
          <div key={status} className="bg-gray-50 rounded-xl p-4 min-h-96">
            <h3 className="font-bold capitalize mb-3">{status.replace('_', ' ')}</h3>
            <div className="space-y-3">
              {complaints
                .filter((c) => c.status === status)
                .map((complaint) => (
                  <div key={complaint.id} className={`${STATUS_COLORS[status]} p-3 rounded-lg text-sm`}>
                    <p className="font-medium">#{complaint.portal_ref}</p>
                    <p className="text-xs opacity-75 mt-1">L{complaint.escalation_level}</p>
                  </div>
                ))}
              {!complaints.some((c) => c.status === status) && (
                <p className="text-gray-400 text-xs text-center py-8">No items</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
