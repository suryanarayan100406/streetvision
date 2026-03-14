import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from 'react-native';
import api from '../api';

export default function ProfileScreen() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/mobile/leaderboard', { params: { limit: 1 } }).then(res => {
      const topEntry = Array.isArray(res.data) ? res.data[0] : null;
      if (topEntry) {
        setProfile({
          username: topEntry.display_name || topEntry.user_id || 'Contributor',
          report_count: topEntry.reports_count,
          total_points: topEntry.total_points,
          rank: topEntry.rank,
          recent_reports: [],
        });
      } else {
        setProfile(null);
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" /></View>;

  return (
    <ScrollView style={styles.container}>
      {profile ? (
        <>
          <View style={styles.header}>
            <Text style={styles.title}>My Contributions</Text>
            <Text style={styles.subtitle}>{profile.username}</Text>
          </View>

          <View style={styles.statsGrid}>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Reports</Text>
              <Text style={styles.statValue}>{profile.report_count}</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Points</Text>
              <Text style={styles.statValue}>{profile.total_points}</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Rank</Text>
              <Text style={styles.statValue}>#{profile.rank}</Text>
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Recent Reports</Text>
            {profile.recent_reports?.map((report, idx) => (
              <View key={idx} style={styles.reportItem}>
                <Text style={styles.reportText}>📍 {report.location}</Text>
                <Text style={styles.reportDate}>{new Date(report.created_at).toLocaleDateString()}</Text>
              </View>
            ))}
          </View>
        </>
      ) : (
        <View style={styles.center}><Text>No profile data</Text></View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f3f4f6' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { marginBottom: 24 },
  title: { fontSize: 24, fontWeight: 'bold' },
  subtitle: { fontSize: 16, color: '#666', marginTop: 4 },
  statsGrid: { flexDirection: 'row', gap: 12, marginBottom: 24 },
  statCard: { flex: 1, backgroundColor: '#fff', padding: 16, borderRadius: 12, alignItems: 'center' },
  statLabel: { fontSize: 12, color: '#999' },
  statValue: { fontSize: 24, fontWeight: 'bold', marginTop: 8 },
  card: { backgroundColor: '#fff', padding: 16, borderRadius: 12, marginBottom: 16 },
  cardTitle: { fontSize: 16, fontWeight: 'bold', marginBottom: 12 },
  reportItem: { paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#eee' },
  reportText: { fontSize: 14, color: '#333' },
  reportDate: { fontSize: 12, color: '#999', marginTop: 4 },
});
