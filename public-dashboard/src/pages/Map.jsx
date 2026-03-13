import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import useFetch from '../hooks/useFetch';

const mapboxToken = import.meta.env.VITE_MAPBOX_TOKEN || '';
const hasMapboxToken = mapboxToken && !mapboxToken.includes('PLACEHOLDER');

if (hasMapboxToken) {
  mapboxgl.accessToken = mapboxToken;
}

export default function Map() {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const { data: geojson } = useFetch('/api/public/geojson');

  useEffect(() => {
    if (!mapContainer.current || !hasMapboxToken) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/streets-v12',
      center: [82.0, 21.5],
      zoom: 7,
    });

    return () => map.current.remove();
  }, []);

  useEffect(() => {
    if (!map.current || !geojson || !hasMapboxToken) return;

    if (map.current.getSource('potholes')) {
      map.current.getSource('potholes').setData(geojson);
    } else {
      map.current.addSource('potholes', { type: 'geojson', data: geojson });
      map.current.addLayer({
        id: 'potholes-layer',
        type: 'circle',
        source: 'potholes',
        paint: {
          'circle-radius': 6,
          'circle-color': [
            'match',
            ['get', 'severity'],
            'Low', '#22c55e',
            'Medium', '#eab308',
            'High', '#f97316',
            'Critical', '#ef4444',
            '#999',
          ],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#fff',
        },
      });
    }

    map.current.on('click', 'potholes-layer', (e) => {
      if (!e.features?.length) return;
      const prop = e.features[0].properties;
      new mapboxgl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(
          `<strong>Pothole #${prop.id}</strong><br/>Severity: ${prop.severity}<br/>Risk: ${prop.risk_score}/100`
        )
        .addTo(map.current);
    });
  }, [geojson]);

  if (!hasMapboxToken) {
    return (
      <div className="bg-white rounded-xl border p-6">
        <h3 className="text-lg font-semibold mb-2">Map unavailable</h3>
        <p className="text-sm text-gray-600">
          Add a valid <code>VITE_MAPBOX_TOKEN</code> in environment to enable map tiles.
        </p>
        <p className="text-sm text-gray-500 mt-2">
          API is still live and detections load via <code>/api/public/geojson</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-8rem)] rounded-xl overflow-hidden shadow-lg border border-gray-200">
      <div ref={mapContainer} className="h-full" />
    </div>
  );
}
