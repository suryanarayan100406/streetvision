import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import * as Location from 'expo-location';
import api from '../api';

export default function MapScreen() {
  const [potholes, setPotholes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      try {
        const permission = await Location.requestForegroundPermissionsAsync();
        if (permission.status === 'granted') {
          const position = await Location.getCurrentPositionAsync({});
          const res = await api.get('/mobile/nearby', {
            params: {
              lat: position.coords.latitude,
              lon: position.coords.longitude,
              radius_m: 1500,
            },
          });
          if (mounted) {
            setPotholes(res.data);
            setError(null);
          }
        } else {
          const res = await api.get('/public/potholes', { params: { limit: 50 } });
          if (mounted) {
            setPotholes(res.data);
            setError('Location access denied. Showing latest potholes instead of nearby ones.');
          }
        }
      } catch (loadError) {
        if (mounted) {
          setError('Pothole data could not be loaded. Check the API host and phone Wi-Fi connection.');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();

    return () => {
      mounted = false;
    };
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
      {error ? <Text style={styles.notice}>{error}</Text> : null}
      <FlatList
        data={potholes}
        keyExtractor={item => item.id.toString()}
        renderItem={({ item }) => (
          <View style={[styles.card, { borderLeftColor: SeverityColor[item.severity] || '#999', borderLeftWidth: 4 }]}>
            <Text style={styles.title}>Pothole #{item.id}</Text>
            <Text style={styles.text}>📍 {item.latitude?.toFixed?.(5) || item.latitude}, {item.longitude?.toFixed?.(5) || item.longitude}</Text>
            <Text style={styles.text}>Severity: {item.severity}</Text>
            <Text style={styles.text}>Risk: {(item.risk_score || 0).toFixed(1)}/100</Text>
            <Text style={styles.text}>Status: {item.status || 'Detected'}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f3f4f6' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  notice: { color: '#92400e', backgroundColor: '#fef3c7', borderRadius: 10, padding: 12, marginBottom: 12 },
  card: { backgroundColor: '#fff', padding: 16, marginBottom: 12, borderRadius: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 1, elevation: 2 },
  title: { fontSize: 16, fontWeight: 'bold', marginBottom: 8 },
  text: { fontSize: 14, color: '#666', marginBottom: 4 },
});
