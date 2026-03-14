import { useEffect, useState } from 'react';

const initialForm = {
  latitude: '',
  longitude: '',
  severity_estimate: 'Medium',
  description: '',
  user_id: '',
  display_name: '',
  device_id: '',
  z_axis_change: '',
};

export default function Crowdsource() {
  const [form, setForm] = useState(initialForm);
  const [imageFile, setImageFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState('');

  const [reports, setReports] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [loadingFeed, setLoadingFeed] = useState(true);

  async function loadFeed() {
    setLoadingFeed(true);
    try {
      const [r1, r2] = await Promise.all([
        fetch('/api/public/crowd/reports?limit=20'),
        fetch('/api/public/crowd/leaderboard?limit=10'),
      ]);

      const reportsData = r1.ok ? await r1.json() : [];
      const leaderboardData = r2.ok ? await r2.json() : [];

      setReports(Array.isArray(reportsData) ? reportsData : []);
      setLeaderboard(Array.isArray(leaderboardData) ? leaderboardData : []);
    } finally {
      setLoadingFeed(false);
    }
  }

  useEffect(() => {
    loadFeed();
  }, []);

  function useMyLocation() {
    if (!navigator.geolocation) {
      setSubmitMessage('Geolocation not supported in this browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm((prev) => ({
          ...prev,
          latitude: String(pos.coords.latitude.toFixed(6)),
          longitude: String(pos.coords.longitude.toFixed(6)),
        }));
      },
      () => {
        setSubmitMessage('Unable to fetch location. Please enter coordinates manually.');
      }
    );
  }

  async function onSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitMessage('');

    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => {
        if ((k === 'z_axis_change' || k === 'device_id') && !String(v).trim()) return;
        fd.append(k, v);
      });
      fd.append('source_type', 'crowd_visual');
      if (imageFile) fd.append('image', imageFile);

      const res = await fetch('/api/public/crowd/report', {
        method: 'POST',
        body: fd,
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to submit report');
      }

      setSubmitMessage(`✅ Submitted report #${data.report_id}. Points earned: ${data.points_earned || 0}`);
      setForm((prev) => ({ ...initialForm, user_id: prev.user_id, display_name: prev.display_name }));
      setImageFile(null);
      await loadFeed();
    } catch (err) {
      setSubmitMessage(`❌ ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Crowdsourcing</h2>
        <button
          onClick={loadFeed}
          className="px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-sm"
          type="button"
        >
          Refresh Feed
        </button>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white border rounded-xl p-5">
          <h3 className="text-lg font-semibold mb-4">Submit pothole report</h3>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="grid sm:grid-cols-2 gap-3">
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="Latitude"
                value={form.latitude}
                onChange={(e) => setForm((p) => ({ ...p, latitude: e.target.value }))}
                required
              />
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="Longitude"
                value={form.longitude}
                onChange={(e) => setForm((p) => ({ ...p, longitude: e.target.value }))}
                required
              />
            </div>

            <button
              type="button"
              onClick={useMyLocation}
              className="px-3 py-2 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-sm"
            >
              Use my location
            </button>

            <div className="grid sm:grid-cols-2 gap-3">
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="User ID (for points)"
                value={form.user_id}
                onChange={(e) => setForm((p) => ({ ...p, user_id: e.target.value }))}
              />
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="Display name"
                value={form.display_name}
                onChange={(e) => setForm((p) => ({ ...p, display_name: e.target.value }))}
              />
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="Device ID (optional)"
                value={form.device_id}
                onChange={(e) => setForm((p) => ({ ...p, device_id: e.target.value }))}
              />
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="Z-axis change (optional)"
                value={form.z_axis_change}
                onChange={(e) => setForm((p) => ({ ...p, z_axis_change: e.target.value }))}
              />
            </div>

            <select
              className="border rounded-lg px-3 py-2 w-full"
              value={form.severity_estimate}
              onChange={(e) => setForm((p) => ({ ...p, severity_estimate: e.target.value }))}
            >
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
              <option value="Critical">Critical</option>
            </select>

            <textarea
              className="border rounded-lg px-3 py-2 w-full"
              rows={3}
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
            />

            <input
              type="file"
              accept="image/*"
              onChange={(e) => setImageFile(e.target.files?.[0] || null)}
              className="block w-full text-sm"
            />

            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300"
            >
              {submitting ? 'Submitting...' : 'Submit Report'}
            </button>

            {submitMessage && (
              <p className="text-sm text-gray-700">{submitMessage}</p>
            )}
          </form>
        </div>

        <div className="bg-white border rounded-xl p-5">
          <h3 className="text-lg font-semibold mb-4">Top Contributors</h3>
          {loadingFeed ? (
            <p className="text-sm text-gray-500">Loading...</p>
          ) : leaderboard.length === 0 ? (
            <p className="text-sm text-gray-500">No contributors yet.</p>
          ) : (
            <div className="space-y-3">
              {leaderboard.map((u) => (
                <div key={u.user_id || u.rank} className="border rounded-lg p-3 flex items-center justify-between">
                  <div>
                    <p className="font-medium">#{u.rank} {u.display_name || u.user_id || 'Anonymous'}</p>
                    <p className="text-xs text-gray-500">{u.reports_count} reports</p>
                  </div>
                  <p className="font-semibold">{u.total_points} pts</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-white border rounded-xl p-5">
        <h3 className="text-lg font-semibold mb-4">Recent Community Reports</h3>
        {loadingFeed ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : reports.length === 0 ? (
          <p className="text-sm text-gray-500">No reports yet.</p>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {reports.map((r) => (
              <div key={r.id} className="border rounded-lg overflow-hidden bg-gray-50">
                {r.image_url ? (
                  <img src={r.image_url} alt={`report-${r.id}`} className="h-40 w-full object-cover" />
                ) : (
                  <div className="h-40 w-full bg-gray-200 flex items-center justify-center text-sm text-gray-500">No image</div>
                )}
                <div className="p-3 space-y-1">
                  <p className="font-semibold">Report #{r.id}</p>
                  <p className="text-xs text-gray-600">{r.source_type}</p>
                  <p className="text-xs text-gray-600">📍 {r.latitude}, {r.longitude}</p>
                  <p className="text-xs text-gray-500">{r.raw_payload?.severity_estimate || 'Unknown'} severity</p>
                  <p className="text-xs text-gray-500 max-h-10 overflow-hidden">{r.raw_payload?.description || 'No description'}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
