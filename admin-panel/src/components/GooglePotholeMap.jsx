import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

function severityColor(severity) {
  switch (severity) {
    case 'Simulated':
      return '#7c3aed';
    case 'Critical':
      return '#dc2626';
    case 'High':
      return '#ea580c';
    case 'Medium':
      return '#ca8a04';
    case 'Low':
      return '#16a34a';
    default:
      return '#2563eb';
  }
}

function roadColor(classification) {
  return classification === 'central' ? '#2563eb' : '#16a34a';
}

export default function GooglePotholeMap({
  geojson,
  highwayGeojson,
  center,
  zoom = 11,
  heightClassName = 'h-full',
  popupLinkPrefix = '/admin',
}) {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) {
      return undefined;
    }

    try {
      mapRef.current = L.map(mapContainer.current, {
        center: center || { lat: 21.5, lng: 82.0 },
        zoom,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(mapRef.current);
    } catch (error) {
      setLoadError(error?.message || 'Unable to load OpenStreetMap.');
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [center, zoom]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    if (layerRef.current) {
      layerRef.current.remove();
    }

    layerRef.current = L.layerGroup().addTo(map);

    const roads = Array.isArray(highwayGeojson?.features) ? highwayGeojson.features : [];
    const potholeFeatures = Array.isArray(geojson?.features) ? geojson.features : [];

    if (roads.length) {
      L.geoJSON(
        {
          type: 'FeatureCollection',
          features: roads,
        },
        {
          style: (feature) => ({
            color: roadColor(feature?.properties?.classification),
            weight: feature?.properties?.classification === 'central' ? 3 : 2,
            opacity: 0.9,
          }),
        }
      ).addTo(layerRef.current);
    }

    const validFeatures = potholeFeatures.filter((feature) => {
      const [lng, lat] = feature.geometry?.coordinates || [];
      return Number.isFinite(lat) && Number.isFinite(lng);
    });

    validFeatures.forEach((feature) => {
      const [lng, lat] = feature.geometry.coordinates;
      const props = feature.properties || {};
      const isSimulated = Boolean(props.simulated);
      const detectedAt = props.detected_at
        ? new Date(props.detected_at).toLocaleString()
        : 'Unknown';
      const detailPath = `${popupLinkPrefix || ''}/detections`;

      const marker = L.circleMarker([lat, lng], {
        radius: 7,
        color: '#ffffff',
        weight: 2,
        fillColor: severityColor(props.severity),
        fillOpacity: 0.95,
      });

      marker.bindPopup(`
        <div style="min-width:220px;font-family:Arial,sans-serif;line-height:1.45">
          <div style="font-size:15px;font-weight:700;margin-bottom:6px">${isSimulated ? 'Simulated Hint' : `Pothole #${props.id ?? 'Unknown'}`}</div>
          <div><strong>Severity:</strong> ${props.severity || 'Unknown'}</div>
          <div><strong>${isSimulated ? 'Probability' : 'Risk'}:</strong> ${Number(props.risk_score || 0).toFixed(1)}/100</div>
          <div><strong>Status:</strong> ${props.status || 'Unknown'}</div>
          <div><strong>Highway:</strong> ${props.nh_number || 'N/A'}</div>
          <div><strong>${isSimulated ? 'Generated' : 'Detected'}:</strong> ${detectedAt}</div>
          ${isSimulated && props.note ? `<div><strong>Note:</strong> ${props.note}</div>` : ''}
          <div style="margin-top:10px;display:flex;gap:12px;flex-wrap:wrap">
            ${isSimulated ? '' : `<a href="${detailPath}" style="color:#1d4ed8;text-decoration:none;font-weight:600">View in admin</a>`}
            <a href="https://www.google.com/maps?q=${lat},${lng}" target="_blank" rel="noreferrer" style="color:#1d4ed8;text-decoration:none;font-weight:600">Open in Google Maps</a>
          </div>
        </div>
      `);

      marker.addTo(layerRef.current);
    });

    if (!validFeatures.length) {
      return;
    }

    if (center) {
      map.setView(center, zoom);
      return;
    }

    if (validFeatures.length === 1) {
      const [lng, lat] = validFeatures[0].geometry.coordinates;
      map.setView([lat, lng], 15);
      return;
    }

    const bounds = L.latLngBounds(
      validFeatures.map((feature) => [feature.geometry.coordinates[1], feature.geometry.coordinates[0]])
    );
    map.fitBounds(bounds, { padding: [56, 56] });
  }, [center, geojson, highwayGeojson, popupLinkPrefix, zoom]);

  if (loadError) {
    return (
      <div className="bg-white rounded-xl border p-6 text-sm text-red-600">
        {loadError}
      </div>
    );
  }

  return <div ref={mapContainer} className={heightClassName} />;
}