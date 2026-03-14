import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
} from 'react-native';
import api from '../api';

// ───────────────── helpers ─────────────────

function Badge({ label, color }) {
  return (
    <View style={[styles.badge, { backgroundColor: color }]}>
      <Text style={styles.badgeText}>{label}</Text>
    </View>
  );
}

const STATUS_COLOR = {
  COMPLETED: '#22c55e',
  PENDING: '#eab308',
  RUNNING: '#3b82f6',
  FAILED: '#ef4444',
  PROCESSING: '#8b5cf6',
  true: '#22c55e',
  false: '#9ca3af',
};

function statusColor(s) {
  return STATUS_COLOR[s] || '#9ca3af';
}

// ───────────────── CCTV tab ─────────────────

function CCTVTab() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true); else setLoading(true);
      const res = await api.get('/public/cctv/nodes?active_only=true');
      setNodes(res.data);
      setError(null);
    } catch (e) {
      setError('Could not load CCTV nodes');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#3b82f6" /></View>;
  if (error) return <View style={styles.center}><Text style={styles.error}>{error}</Text></View>;
  if (nodes.length === 0) return <View style={styles.center}><Text style={styles.empty}>No active CCTV cameras found</Text></View>;

  return (
    <FlatList
      data={nodes}
      keyExtractor={item => item.id.toString()}
      contentContainerStyle={styles.list}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />}
      renderItem={({ item }) => (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>📷 {item.name}</Text>
            <Badge label={item.is_active ? 'Active' : 'Inactive'} color={statusColor(item.is_active)} />
          </View>
          {item.nh_number && (
            <Text style={styles.cardText}>🛣️ NH {item.nh_number}{item.chainage_km ? ` — km ${item.chainage_km}` : ''}</Text>
          )}
          {item.latitude && item.longitude && (
            <Text style={styles.cardText}>📍 {item.latitude.toFixed(5)}, {item.longitude.toFixed(5)}</Text>
          )}
          {item.last_frame_at && (
            <Text style={styles.cardSub}>Last frame: {new Date(item.last_frame_at).toLocaleString()}</Text>
          )}
        </View>
      )}
    />
  );
}

// ───────────────── Drone tab ─────────────────

function DroneTab() {
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true); else setLoading(true);
      const res = await api.get('/public/drones/missions?limit=50');
      setMissions(res.data);
      setError(null);
    } catch (e) {
      setError('Could not load drone missions');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#3b82f6" /></View>;
  if (error) return <View style={styles.center}><Text style={styles.error}>{error}</Text></View>;
  if (missions.length === 0) return <View style={styles.center}><Text style={styles.empty}>No drone missions found</Text></View>;

  return (
    <FlatList
      data={missions}
      keyExtractor={item => item.id.toString()}
      contentContainerStyle={styles.list}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />}
      renderItem={({ item }) => (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>🚁 {item.mission_name || `Mission #${item.id}`}</Text>
            <Badge label={item.processing_status} color={statusColor(item.processing_status)} />
          </View>
          {item.operator && <Text style={styles.cardText}>👤 {item.operator}</Text>}
          {item.flight_date && <Text style={styles.cardText}>📅 {item.flight_date}</Text>}
          {item.image_count != null && (
            <Text style={styles.cardText}>🖼 {item.image_count} images{item.gsd_cm ? ` @ ${item.gsd_cm} cm/px` : ''}</Text>
          )}
          <Text style={styles.cardSub}>Created: {new Date(item.created_at).toLocaleDateString()}</Text>
          {item.completed_at && (
            <Text style={styles.cardSub}>Completed: {new Date(item.completed_at).toLocaleDateString()}</Text>
          )}
        </View>
      )}
    />
  );
}

// ───────────────── Satellite tab ─────────────────

function SatelliteTab() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true); else setLoading(true);
      const res = await api.get('/public/satellites/jobs?limit=50');
      setJobs(res.data);
      setError(null);
    } catch (e) {
      setError('Could not load satellite jobs');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#3b82f6" /></View>;
  if (error) return <View style={styles.center}><Text style={styles.error}>{error}</Text></View>;
  if (jobs.length === 0) return <View style={styles.center}><Text style={styles.empty}>No satellite jobs found</Text></View>;

  return (
    <FlatList
      data={jobs}
      keyExtractor={item => item.id.toString()}
      contentContainerStyle={styles.list}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />}
      renderItem={({ item }) => {
        const isMonitoringOnly = item.monitoring_only_tiles > 0 && item.tiles_forwarded_to_inference === 0;
        return (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>🛰️ Satellite Job #{item.id}</Text>
              <Badge label={item.status} color={statusColor(item.status)} />
            </View>
            <View style={styles.row}>
              <Badge
                label={isMonitoringOnly ? `Monitoring (${item.monitoring_only_tiles})` : `Inference (${item.tiles_forwarded_to_inference})`}
                color={isMonitoringOnly ? '#f59e0b' : '#3b82f6'}
              />
            </View>
            <Text style={styles.cardText}>
              Tiles: {item.tiles_processed}/{item.tiles_total}
            </Text>
            {item.detections_count > 0 && (
              <Text style={styles.cardText}>⚠️ {item.detections_count} detections</Text>
            )}
            <Text style={styles.cardSub}>Started: {new Date(item.created_at).toLocaleString()}</Text>
            {item.completed_at && (
              <Text style={styles.cardSub}>Completed: {new Date(item.completed_at).toLocaleString()}</Text>
            )}
          </View>
        );
      }}
    />
  );
}

// ───────────────── Main DataScreen ─────────────────

const TABS = [
  { key: 'cctv', label: '📷 CCTV' },
  { key: 'drone', label: '🚁 Drone' },
  { key: 'satellite', label: '🛰️ Satellite' },
];

export default function DataScreen() {
  const [activeTab, setActiveTab] = useState('cctv');

  return (
    <View style={styles.screen}>
      {/* Tab bar */}
      <View style={styles.tabBar}>
        {TABS.map(tab => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tabButton, activeTab === tab.key && styles.tabButtonActive]}
            onPress={() => setActiveTab(tab.key)}
          >
            <Text style={[styles.tabLabel, activeTab === tab.key && styles.tabLabelActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Tab content */}
      <View style={styles.tabContent}>
        {activeTab === 'cctv' && <CCTVTab />}
        {activeTab === 'drone' && <DroneTab />}
        {activeTab === 'satellite' && <SatelliteTab />}
      </View>
    </View>
  );
}

// ───────────────── styles ─────────────────

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#f3f4f6' },

  // Tab bar
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  tabButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
  },
  tabButtonActive: {
    borderBottomWidth: 2,
    borderBottomColor: '#3b82f6',
  },
  tabLabel: { fontSize: 13, color: '#9ca3af', fontWeight: '500' },
  tabLabelActive: { color: '#3b82f6', fontWeight: '700' },

  // Content area
  tabContent: { flex: 1 },
  list: { padding: 16 },

  // Card
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  cardTitle: { fontSize: 15, fontWeight: '700', color: '#1f2937', flex: 1, marginRight: 8 },
  cardText: { fontSize: 13, color: '#4b5563', marginBottom: 3 },
  cardSub: { fontSize: 11, color: '#9ca3af', marginTop: 2 },
  row: { flexDirection: 'row', marginBottom: 6 },

  // Badge
  badge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  badgeText: { color: '#fff', fontSize: 11, fontWeight: '600' },

  // States
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  error: { color: '#ef4444', textAlign: 'center', fontSize: 14 },
  empty: { color: '#9ca3af', textAlign: 'center', fontSize: 14 },
});
