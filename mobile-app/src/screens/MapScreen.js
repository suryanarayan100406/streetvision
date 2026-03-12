import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import api from '../api';

export default function MapScreen() {
  const [potholes, setPotholes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/public/list').then(res => {
      setPotholes(res.data);
      setLoading(false);
    });
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" /></View>;

  const SeverityColor = {
    'Low': '#22c55e',
    'Medium': '#eab308',
    'High': '#f97316',
    'Critical': '#ef4444',
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={potholes}
        keyExtractor={item => item.id.toString()}
        renderItem={({ item }) => (
          <View style={[styles.card, { borderLeftColor: SeverityColor[item.severity] || '#999', borderLeftWidth: 4 }]}>
            <Text style={styles.title}>Pothole #{item.id}</Text>
            <Text style={styles.text}>📍 {item.location_name}</Text>
            <Text style={styles.text}>Severity: {item.severity}</Text>
            <Text style={styles.text}>Risk: {item.risk_score.toFixed(1)}/100</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f3f4f6' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  card: { backgroundColor: '#fff', padding: 16, marginBottom: 12, borderRadius: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 1, elevation: 2 },
  title: { fontSize: 16, fontWeight: 'bold', marginBottom: 8 },
  text: { fontSize: 14, color: '#666', marginBottom: 4 },
});
