import { useFetch } from '../hooks/useFetch';
import GooglePotholeMap from '../components/GooglePotholeMap';

export default function ModuleInferenceDecision() {
  const { data, loading, error, refetch } = useFetch('/admin/inference/overview');
  const { data: geojson } = useFetch('/public/geojson');

  const decisionIds = new Set((data?.recent_decisions || []).map((row) => Number(row.pothole_id)));
  const decisionGeojson = {
    type: 'FeatureCollection',
    features: (geojson?.features || []).filter((feature) => decisionIds.has(Number(feature.properties?.id))),
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Module · Inference Decision Engine</h2>
        <button onClick={refetch} className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading inference diagnostics...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <>
          <div className="bg-white border rounded-xl p-4 mb-6">
            <h3 className="font-semibold mb-3">A) Active Models (YOLO → MiDaS → Verifier)</h3>
            <div className="grid md:grid-cols-3 gap-3 text-sm">
              {(data.models || []).map((m) => (
                <div key={`${m.model_type}-${m.version}`} className="border rounded p-3">
                  <p className="text-gray-500">{m.model_type}</p>
                  <p className="font-semibold">{m.model_name}</p>
                  <p className="text-xs text-gray-500">v{m.version || '-'}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Samples</p>
              <p className="text-2xl font-bold">{data.summary?.rows ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Auto File</p>
              <p className="text-2xl font-bold">{data.summary?.auto_file ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Manual Review</p>
              <p className="text-2xl font-bold">{data.summary?.review ?? 0}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-500">Monitor</p>
              <p className="text-2xl font-bold">{data.summary?.monitor ?? 0}</p>
            </div>
          </div>

          <div className="bg-white rounded-xl border overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 font-semibold text-sm">B) Stage Outputs (YOLO, Depth, Classifier, Confidence, Decision)</div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3">Pothole</th>
                  <th className="text-left px-4 py-3">Source</th>
                  <th className="text-left px-4 py-3">YOLO Conf</th>
                  <th className="text-left px-4 py-3">Depth (cm)</th>
                  <th className="text-left px-4 py-3">Area (m²)</th>
                  <th className="text-left px-4 py-3">Severity</th>
                  <th className="text-left px-4 py-3">Fused Conf</th>
                  <th className="text-left px-4 py-3">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {(data.recent_decisions || []).map((row) => (
                  <tr key={row.pothole_id}>
                    <td className="px-4 py-3">{row.pothole_id}</td>
                    <td className="px-4 py-3">{row.source_type || '-'}</td>
                    <td className="px-4 py-3">{(Number(row.yolo_confidence || 0) * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3">{Number(row.depth_cm || 0).toFixed(2)}</td>
                    <td className="px-4 py-3">{Number(row.area_m2 || 0).toFixed(4)}</td>
                    <td className="px-4 py-3">{row.severity || '-'}</td>
                    <td className="px-4 py-3">{(Number(row.fused_confidence || 0) * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3">{row.decision_action || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white border rounded-xl p-4 mt-6">
            <h3 className="font-semibold mb-3">C) Decision Samples on Map</h3>
            <p className="text-sm text-gray-500 mb-3">
              Exact locations for the latest inference decisions.
            </p>
            <div className="h-80 overflow-hidden rounded-lg border border-gray-200">
              <GooglePotholeMap
                geojson={decisionGeojson}
                heightClassName="h-full w-full"
                popupLinkPrefix="/admin"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
