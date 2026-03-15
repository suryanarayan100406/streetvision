import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import api from '../api';

export default function LeaderboardScreen() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const loadLeaderboard = async (asRefresh = false, aliveRef = { current: true }) => {
    if (asRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const res = await api.get('/mobile/leaderboard');
      if (!aliveRef.current) return;
      const rows = Array.isArray(res.data) ? res.data : [];
      setUsers(rows);
      setError(null);
    } catch {
      if (!aliveRef.current) return;
      setError('Leaderboard could not be loaded. Please check your connection and API host.');
    } finally {
      if (!aliveRef.current) return;
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const aliveRef = { current: true };
    loadLeaderboard(false, aliveRef);
    return () => {
      aliveRef.current = false;
    };
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" /></View>;
  if (error) return <View style={styles.center}><Text style={styles.error}>{error}</Text></View>;

  if (!users.length) {
    return (
      <View style={styles.center}>
        <Text style={styles.emptyTitle}>No leaderboard entries yet</Text>
        <Text style={styles.emptyText}>Submit reports from the Report tab after signing in from Profile.</Text>
      </View>
    );
  }

  const medals = ['🥇', '🥈', '🥉'];

  return (
    <View style={styles.container}>
      <FlatList
        data={users}
        keyExtractor={(item, index) => String(item.user_id || item.rank || index)}
        onRefresh={() => loadLeaderboard(true, { current: true })}
        refreshing={refreshing}
        renderItem={({ item, index }) => (
          <View style={styles.card}>
            <Text style={styles.medal}>{medals[index] || `#${index + 1}`}</Text>
            <View style={styles.cardContent}>
              <Text style={styles.username}>{item.display_name || item.user_id || 'Anonymous user'}</Text>
              <Text style={styles.stats}>{item.reports_count || 0} reports • {item.total_points || 0} pts</Text>
            </View>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f3f4f6' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  error: { color: '#dc2626', fontSize: 14, paddingHorizontal: 16, textAlign: 'center' },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: '#111827' },
  emptyText: { marginTop: 8, color: '#6b7280', textAlign: 'center', paddingHorizontal: 20 },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', padding: 16, marginBottom: 12, borderRadius: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 1, elevation: 2 },
  medal: { fontSize: 32, marginRight: 16 },
  cardContent: { flex: 1 },
  username: { fontSize: 16, fontWeight: 'bold' },
  stats: { fontSize: 13, color: '#999', marginTop: 4 },
});
