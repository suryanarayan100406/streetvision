import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import api from '../api';

export default function LeaderboardScreen() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/public/leaderboard').then(res => {
      setUsers(res.data);
      setLoading(false);
    });
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" /></View>;

  const medals = ['🥇', '🥈', '🥉'];

  return (
    <View style={styles.container}>
      <FlatList
        data={users}
        keyExtractor={item => item.id.toString()}
        renderItem={({ item, index }) => (
          <View style={styles.card}>
            <Text style={styles.medal}>{medals[index] || `#${index + 1}`}</Text>
            <View style={styles.cardContent}>
              <Text style={styles.username}>{item.username}</Text>
              <Text style={styles.stats}>{item.report_count} reports • {item.total_points} pts</Text>
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
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', padding: 16, marginBottom: 12, borderRadius: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 1, elevation: 2 },
  medal: { fontSize: 32, marginRight: 16 },
  cardContent: { flex: 1 },
  username: { fontSize: 16, fontWeight: 'bold' },
  stats: { fontSize: 13, color: '#999', marginTop: 4 },
});
