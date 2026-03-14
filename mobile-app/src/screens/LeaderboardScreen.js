import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import api from '../api';

export default function LeaderboardScreen() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    api.get('/mobile/leaderboard').then(res => {
      if (!mounted) return;
      setUsers(res.data);
      setError(null);
      setLoading(false);
    }).catch(() => {
      if (!mounted) return;
      setError('Leaderboard could not be loaded.');
      setLoading(false);
    });

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" /></View>;
  if (error) return <View style={styles.center}><Text style={styles.error}>{error}</Text></View>;

  const medals = ['🥇', '🥈', '🥉'];

  return (
    <View style={styles.container}>
      <FlatList
        data={users}
        keyExtractor={item => String(item.user_id || item.rank)}
        renderItem={({ item, index }) => (
          <View style={styles.card}>
            <Text style={styles.medal}>{medals[index] || `#${index + 1}`}</Text>
            <View style={styles.cardContent}>
              <Text style={styles.username}>{item.display_name || item.user_id || 'Anonymous user'}</Text>
              <Text style={styles.stats}>{item.reports_count} reports • {item.total_points} pts</Text>
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
  error: { color: '#dc2626', fontSize: 14 },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', padding: 16, marginBottom: 12, borderRadius: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 1, elevation: 2 },
  medal: { fontSize: 32, marginRight: 16 },
  cardContent: { flex: 1 },
  username: { fontSize: 16, fontWeight: 'bold' },
  stats: { fontSize: 13, color: '#999', marginTop: 4 },
});
