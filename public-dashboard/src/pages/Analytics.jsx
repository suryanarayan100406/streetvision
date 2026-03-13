import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import useFetch from '../hooks/useFetch';

const SEVERITY_COLORS = {
  Low: '#22c55e',
  Medium: '#eab308',
  High: '#f97316',
  Critical: '#ef4444',
};

export default function Analytics() {
  const { data: trend } = useFetch('/api/dashboard/trend');
  const { data: severity } = useFetch('/api/dashboard/severity-distribution');
  const { data: funnel } = useFetch('/api/dashboard/complaint-funnel');
  const { data: highways } = useFetch('/api/dashboard/highway-comparison');

  const severityData = severity
    ? Object.entries(severity).map(([severityName, count]) => ({ severity: severityName, count }))
    : [];

  const funnelData = funnel
    ? [
      { status: 'detected', count: funnel.detected || 0 },
      { status: 'filed', count: funnel.filed || 0 },
      { status: 'acknowledged', count: funnel.acknowledged || 0 },
      { status: 'resolved', count: funnel.resolved || 0 },
    ]
    : [];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Analytics Dashboard</h2>

      {/* Trend Chart */}
      {trend && (
        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-bold mb-4">Detections Over Time (30 Days)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="count" stroke="#3b82f6" name="Detections" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Severity Distribution */}
        {severityData.length > 0 && (
          <div className="bg-white rounded-xl border p-6">
            <h3 className="font-bold mb-4">Severity Breakdown</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={severityData} dataKey="count" nameKey="severity" label outerRadius={80}>
                  {severityData.map((entry, idx) => (
                    <Cell key={idx} fill={SEVERITY_COLORS[entry.severity] || '#999'} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Highway Comparison */}
        {highways && (
          <div className="bg-white rounded-xl border p-6">
            <h3 className="font-bold mb-4">Potholes by Highway</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={highways}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="nh_number" angle={-45} textAnchor="end" height={80} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="total" fill="#8b5cf6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Complaint Funnel */}
      {funnelData.length > 0 && (
        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-bold mb-4">Complaint Status Funnel</h3>
          <div className="space-y-2">
            {funnelData.map((stage, idx) => (
              <div key={stage.status}>
                <p className="text-sm font-medium capitalize mb-1">{stage.status.replace('_', ' ')}</p>
                <div className="bg-gray-200 rounded-full h-8 flex items-center" style={{ width: `${funnelData[0]?.count ? (stage.count / funnelData[0].count) * 100 : 0}%` }}>
                  <span className="text-xs font-bold text-white px-3">{stage.count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
