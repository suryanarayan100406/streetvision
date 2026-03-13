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
  const { data: funnel } = useFetch('/api/dashboard/complaint-funnel');

  if (!funnel) return <div className="text-center py-8">Loading...</div>;

  const complaintStages = [
    { status: 'new', count: funnel.detected || 0 },
    { status: 'investigating', count: funnel.filed || 0 },
    { status: 'in_repair', count: funnel.acknowledged || 0 },
    { status: 'resolved', count: funnel.resolved || 0 },
    { status: 'failed', count: Math.max((funnel.detected || 0) - (funnel.resolved || 0), 0) },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Complaint Resolution Pipeline</h2>
      <div className="grid lg:grid-cols-5 gap-4">
        {STATUSES.map((status) => (
          <div key={status} className="bg-gray-50 rounded-xl p-4 min-h-96">
            <h3 className="font-bold capitalize mb-3">{status.replace('_', ' ')}</h3>
            <div className="space-y-3">
              <div className={`${STATUS_COLORS[status]} p-3 rounded-lg text-sm`}>
                <p className="font-medium">{complaintStages.find((s) => s.status === status)?.count || 0} items</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
