import { useParams } from 'react-router-dom';
import useFetch from '../hooks/useFetch';
import GooglePotholeMap from '../components/GooglePotholeMap';

export default function PotholeDetail() {
  const { id } = useParams();
  const { data: pothole } = useFetch(`/api/public/potholes/${id}`);

  if (!pothole) return <div className="text-center py-8">Loading...</div>;

  const lat = Number(pothole.latitude);
  const lng = Number(pothole.longitude);
  const hasCoordinates = Number.isFinite(lat) && Number.isFinite(lng);
  const detailGeojson = hasCoordinates
    ? {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [lng, lat],
            },
            properties: {
              id: pothole.id,
              severity: pothole.severity,
              risk_score: pothole.risk_score,
              status: pothole.status,
              nh_number: pothole.nh_number,
              detected_at: pothole.detected_at,
            },
          },
        ],
      }
    : null;

  return (
    <div className="grid lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <div className="bg-white rounded-xl border p-6">
          <h2 className="text-2xl font-bold mb-2">Pothole #{pothole.id}</h2>
          <p className="text-gray-600 mb-4">{pothole.district || pothole.nh_number || 'Unknown location'}</p>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Severity</p>
              <p className="text-lg font-bold">{pothole.severity || 'N/A'}</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Risk Score</p>
              <p className="text-lg font-bold">{Number(pothole.risk_score || 0).toFixed(1)}/100</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Diameter (cm)</p>
              <p className="text-lg font-bold">{pothole.estimated_diameter_m ? `${pothole.estimated_diameter_m} m` : 'N/A'}</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Depth (cm)</p>
              <p className="text-lg font-bold">{pothole.estimated_depth_cm ? Number(pothole.estimated_depth_cm).toFixed(1) : 'N/A'}</p>
            </div>
          </div>

          <div className="space-y-2">
            <p><strong>Status:</strong> {pothole.status}</p>
            <p><strong>Detected:</strong> {new Date(pothole.detected_at).toLocaleDateString()}</p>
            <p><strong>Highway:</strong> {pothole.nh_number || 'N/A'}</p>
            <p><strong>Confidence:</strong> {(Number(pothole.confidence_score || 0) * 100).toFixed(1)}%</p>
            <p><strong>Coordinates:</strong> {hasCoordinates ? `${lat.toFixed(6)}, ${lng.toFixed(6)}` : 'N/A'}</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border p-6 mt-6">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Exact location</h3>
              <p className="text-sm text-gray-600">Stored pothole coordinates rendered on the map.</p>
            </div>
            {hasCoordinates ? (
              <a
                href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=17/${lat}/${lng}`}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-semibold text-blue-700 hover:text-blue-900"
              >
                Open in OpenStreetMap
              </a>
            ) : null}
          </div>

          {hasCoordinates ? (
            <div className="h-80 overflow-hidden rounded-lg border border-gray-200">
              <GooglePotholeMap
                geojson={detailGeojson}
                center={{ lat, lng }}
                zoom={17}
                heightClassName="h-full w-full"
              />
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-600">
              Coordinates are not available for this pothole yet.
            </div>
          )}
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
                <span className="text-gray-500">+{(Number(src.confidence_boost || 0) * 100).toFixed(0)}% boost</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-bold mb-3">Associated Complaint</h3>
          {pothole.complaints?.[0] ? (
            <div className="text-sm space-y-1">
              <p><strong>ID:</strong> {pothole.complaints[0].portal_ref}</p>
              <p><strong>Status:</strong> {pothole.complaints[0].portal_status || 'N/A'}</p>
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
