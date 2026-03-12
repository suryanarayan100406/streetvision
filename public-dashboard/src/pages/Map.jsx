import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import useFetch from '../hooks/useFetch';

mapboxgl.accessToken = 'pk.eyJ1IjoiY2doYXNzYW0iLCJhIjoiY20zMDA0aHd5MDAwZDJsbXh4a3lzMDAxdyJ9.PLACEHOLDER';

export default function Map() {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const { data: geojson } = useFetch('/api/public/geojson');

  useEffect(() => {
    if (!mapContainer.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/streets-v12',
      center: [82.0, 21.5],
      zoom: 7,
    });

    return () => map.current.remove();
  }, []);

  useEffect(() => {
    if (!map.current || !geojson) return;

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
      const prop = e.features[0].properties;
      new mapboxgl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(
          `<strong>Pothole #${prop.id}</strong><br/>Severity: ${prop.severity}<br/>Risk: ${prop.risk_score}/100`
        )
        .addTo(map.current);
    });
  }, [geojson]);

  return (
    <div className="h-[calc(100vh-8rem)] rounded-xl overflow-hidden shadow-lg border border-gray-200">
      <div ref={mapContainer} className="h-full" />
    </div>
  );
}
