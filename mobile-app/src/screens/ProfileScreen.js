import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, TextInput, TouchableOpacity } from 'react-native';
import api from '../api';
import { clearStoredProfile, getStoredProfile, setStoredProfile } from '../userProfileStore';

export default function ProfileScreen() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loginUserId, setLoginUserId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [authError, setAuthError] = useState('');

  const loadProfile = async (explicitUserId) => {
    const stored = await getStoredProfile();
    const userId = explicitUserId || stored?.user_id;
    if (!userId) {
      setProfile(null);
      setLoading(false);
      return;
    }

    try {
      const res = await api.get('/mobile/profile/me', { params: { user_id: userId } });
      const payload = res.data || {};
      setProfile(payload);
      setLoginUserId(payload.user_id || userId);
      setDisplayName(payload.display_name || payload.user_id || '');
      await setStoredProfile({
        user_id: payload.user_id || userId,
        display_name: payload.display_name || payload.user_id || userId,
      });
    } catch {
      setAuthError('Profile could not be loaded. Please sign in again.');
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleLogin = async () => {
    const userId = (loginUserId || '').trim();
    const name = (displayName || '').trim();
    if (!userId) {
      setAuthError('User ID is required.');
      return;
    }

    setLoading(true);
    setAuthError('');
    try {
      const formData = new FormData();
      formData.append('user_id', userId);
      formData.append('display_name', name || userId);
      const res = await api.post('/mobile/profile/login', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const payload = res.data || {};
      await setStoredProfile({
        user_id: payload.user_id || userId,
        display_name: payload.display_name || name || userId,
      });
      await loadProfile(payload.user_id || userId);
    } catch (e) {
      setAuthError(e?.response?.data?.detail || 'Sign-in failed. Please try again.');
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await clearStoredProfile();
    setProfile(null);
    setLoginUserId('');
    setDisplayName('');
    setAuthError('');
  };

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" /></View>;

  return (
    <ScrollView style={styles.container}>
      {profile ? (
        <>
          <View style={styles.header}>
            <Text style={styles.title}>My Contributions</Text>
            <Text style={styles.subtitle}>{profile.display_name || profile.user_id}</Text>
            <Text style={styles.caption}>User ID: {profile.user_id}</Text>
          </View>

          <View style={styles.statsGrid}>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Reports</Text>
              <Text style={styles.statValue}>{profile.reports_count || 0}</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Points</Text>
              <Text style={styles.statValue}>{profile.total_points || 0}</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Rank</Text>
              <Text style={styles.statValue}>{profile.rank ? `#${profile.rank}` : '-'}</Text>
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Account</Text>
            <Text style={styles.reportText}>Use the same User ID in reports to accumulate points and rank.</Text>
            <TouchableOpacity style={[styles.button, styles.logoutButton]} onPress={handleLogout}>
              <Text style={styles.buttonText}>Log out</Text>
            </TouchableOpacity>
          </View>
        </>
      ) : (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Sign in</Text>
          <Text style={styles.subtitle}>Create a lightweight mobile profile</Text>
          <TextInput
            placeholder="User ID (e.g. driver_27)"
            value={loginUserId}
            onChangeText={setLoginUserId}
            style={styles.input}
            autoCapitalize="none"
          />
          <TextInput
            placeholder="Display name"
            value={displayName}
            onChangeText={setDisplayName}
            style={styles.input}
          />
          {authError ? <Text style={styles.error}>{authError}</Text> : null}
          <TouchableOpacity style={[styles.button, styles.loginButton]} onPress={handleLogin}>
            <Text style={styles.buttonText}>Sign in</Text>
          </TouchableOpacity>
        </View>
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
  caption: { fontSize: 12, color: '#888', marginTop: 2 },
  statsGrid: { flexDirection: 'row', gap: 12, marginBottom: 24 },
  statCard: { flex: 1, backgroundColor: '#fff', padding: 16, borderRadius: 12, alignItems: 'center' },
  statLabel: { fontSize: 12, color: '#999' },
  statValue: { fontSize: 24, fontWeight: 'bold', marginTop: 8 },
  card: { backgroundColor: '#fff', padding: 16, borderRadius: 12, marginBottom: 16 },
  cardTitle: { fontSize: 16, fontWeight: 'bold', marginBottom: 12 },
  input: { borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, marginTop: 10, backgroundColor: '#fff' },
  error: { color: '#dc2626', marginTop: 10 },
  button: { marginTop: 14, borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  loginButton: { backgroundColor: '#2563eb' },
  logoutButton: { backgroundColor: '#ef4444' },
  buttonText: { color: '#fff', fontWeight: '700' },
  reportItem: { paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#eee' },
  reportText: { fontSize: 14, color: '#333' },
  reportDate: { fontSize: 12, color: '#999', marginTop: 4 },
});
