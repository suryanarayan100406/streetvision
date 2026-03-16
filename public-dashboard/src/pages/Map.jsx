import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import useFetch from '../hooks/useFetch';
import GooglePotholeMap from '../components/GooglePotholeMap';

export default function Map() {
  const { data: geojson } = useFetch('/api/public/geojson');
  const { data: highwaysGeojson } = useFetch('/api/public/highways/geojson?road_type=all&chhattisgarh_only=true');
  const features = geojson?.features || [];
  const exactLocations = features.filter((feature) => {
    const coordinates = feature.geometry?.coordinates || [];
    return Number.isFinite(coordinates[0]) && Number.isFinite(coordinates[1]);
  });
  const criticalCount = features.filter((feature) => feature.properties?.severity === 'Critical').length;
  const listGeojson = useMemo(() => ({
    type: 'FeatureCollection',
    features: exactLocations,
  }), [exactLocations]);

  return (
    <section className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Tracked potholes</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{features.length}</p>
          <p className="mt-1 text-sm text-gray-600">Every marker comes from stored pothole coordinates.</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Critical cases</p>
          <p className="mt-2 text-3xl font-bold text-red-600">{criticalCount}</p>
          <p className="mt-1 text-sm text-gray-600">High-priority markers remain color-coded on the map.</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Map engine</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">Central + State Highways</p>
          <p className="mt-1 text-sm text-gray-600">
            Central roads are blue, state roads are green, with exact pothole positions overlaid.
          </p>
        </div>
      </div>

      <div className="h-[calc(100vh-14rem)] rounded-xl overflow-hidden border border-gray-200 shadow-lg bg-white">
        <GooglePotholeMap geojson={listGeojson} highwayGeojson={highwaysGeojson} heightClassName="h-full w-full" />
      </div>

      <div className="flex items-center gap-4 text-xs text-gray-700">
        <span className="inline-flex items-center gap-2"><span className="inline-block h-2.5 w-5 rounded bg-blue-600" /> Central highway</span>
        <span className="inline-flex items-center gap-2"><span className="inline-block h-2.5 w-5 rounded bg-green-600" /> State highway</span>
      </div>

      <div className="bg-white rounded-xl border p-6">
        <h3 className="text-lg font-semibold mb-4">Latest exact locations</h3>
        <div className="space-y-3">
          {exactLocations.slice(0, 12).map((feature) => {
            const [lng, lat] = feature.geometry.coordinates;
            return (
              <div key={feature.properties.id} className="rounded-lg border border-gray-200 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold text-gray-900">Pothole #{feature.properties.id}</p>
                    <p className="text-sm text-gray-600">
                      {Number(lat).toFixed(6)}, {Number(lng).toFixed(6)}
                    </p>
                  </div>
                  <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                    {feature.properties.severity || 'Unknown'}
                  </span>
                </div>
                <div className="mt-3 flex gap-4 text-sm font-medium">
                  <Link to={`/pothole/${feature.properties.id}`} className="text-blue-700 hover:text-blue-900">
                    View details
                  </Link>
                  <a
                    href={`https://www.google.com/maps?q=${lat},${lng}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-700 hover:text-blue-900"
                  >
                    Open in Google Maps
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
