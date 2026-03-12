import { useParams } from 'react-router-dom';
import useFetch from '../hooks/useFetch';

export default function PotholeDetail() {
  const { id } = useParams();
  const { data: pothole } = useFetch(`/api/public/pothole/${id}`);

  if (!pothole) return <div className="text-center py-8">Loading...</div>;

  return (
    <div className="grid lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <div className="bg-white rounded-xl border p-6">
          <h2 className="text-2xl font-bold mb-2">Pothole #{pothole.id}</h2>
          <p className="text-gray-600 mb-4">{pothole.location_name}</p>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Severity</p>
              <p className={`text-lg font-bold severity-${pothole.severity.toLowerCase()}`}>{pothole.severity}</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Risk Score</p>
              <p className="text-lg font-bold">{pothole.risk_score.toFixed(1)}/100</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Diameter (cm)</p>
              <p className="text-lg font-bold">{pothole.diameter_cm}</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Depth (cm)</p>
              <p className="text-lg font-bold">{pothole.depth_cm.toFixed(1)}</p>
            </div>
          </div>

          <div className="space-y-2">
            <p><strong>Status:</strong> {pothole.status}</p>
            <p><strong>Detected:</strong> {new Date(pothole.detected_at).toLocaleDateString()}</p>
            <p><strong>Road:</strong> {pothole.road_id}</p>
            <p><strong>Confidence:</strong> {(pothole.confidence_score * 100).toFixed(1)}%</p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-bold mb-3">Evidence Sources</h3>
          <ul className="space-y-2 text-sm">
            {pothole.source_reports?.map((src) => (
              <li key={src.id} className="p-2 bg-gray-50 rounded">
                📷 {src.source_type}
                <br />
                <span className="text-gray-500">+{(src.confidence_boost * 100).toFixed(0)}% boost</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-bold mb-3">Associated Complaint</h3>
          {pothole.complaints?.[0] ? (
            <div className="text-sm space-y-1">
              <p><strong>ID:</strong> {pothole.complaints[0].portal_ref}</p>
              <p><strong>Status:</strong> {pothole.complaints[0].status}</p>
              <p><strong>Level:</strong> {pothole.complaints[0].escalation_level}</p>
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No complaint filed yet</p>
          )}
        </div>
      </div>
    </div>
  );
}
