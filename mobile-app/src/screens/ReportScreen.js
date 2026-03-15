import React, { useState, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Image, Alert } from 'react-native';
import { Camera } from 'expo-camera';
import * as Location from 'expo-location';
import { Accelerometer } from 'expo-sensors';
import api from '../api';
import { getApiBaseUrl } from '../api';
import { getStoredProfile } from '../userProfileStore';

const AUTO_REPORT_Z_THRESHOLD = 1.05;
const AUTO_REPORT_MIN_SPEED_KMH = 0.0;
const AUTO_REPORT_MIN_VARIANCE = 0.12;
const AUTO_REPORT_COOLDOWN_MS = 7000;
const SENSOR_WINDOW_SIZE = 8;
const DEMO_SEND_MIN_SPEED_KMH = 12.0;

function clampMagnitude(value) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(50, value));
}

function calculateVariance(samples) {
  if (!samples.length) return 0;
  const mean = samples.reduce((sum, sample) => sum + sample, 0) / samples.length;
  const squared = samples.reduce((sum, sample) => sum + ((sample - mean) ** 2), 0) / samples.length;
  return Math.sqrt(squared);
}

export default function ReportScreen() {
  const backType = Camera?.Constants?.Type?.back ?? 'back';
  const frontType = Camera?.Constants?.Type?.front ?? 'front';
  const [hasPermission, setHasPermission] = useState(null);
  const [type, setType] = useState(backType);
  const [photo, setPhoto] = useState(null);
  const [loading, setLoading] = useState(false);
  const [locationPermission, setLocationPermission] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [autoDetectEnabled, setAutoDetectEnabled] = useState(true);
  const [shakeNotice, setShakeNotice] = useState({
    visible: false,
    level: 'info',
    message: '',
    sending: false,
  });
  const [motionState, setMotionState] = useState({
    speedKmh: 0,
    zAxisChange: 0,
    variance: 0,
    lastStatus: 'Waiting for motion data',
  });
  const cameraRef = useRef(null);
  const noticeTimerRef = useRef(null);
  const recentZValuesRef = useRef([]);
  const lastLocationRef = useRef(null);
  const lastAutoSubmitRef = useRef(0);

  const showShakeNotice = (level, message, sending = false, ttlMs = 2600) => {
    if (noticeTimerRef.current) {
      clearTimeout(noticeTimerRef.current);
    }
    setShakeNotice({ visible: true, level, message, sending });
    if (ttlMs > 0) {
      noticeTimerRef.current = setTimeout(() => {
        setShakeNotice((prev) => ({ ...prev, visible: false, sending: false }));
      }, ttlMs);
    }
  };

  React.useEffect(() => {
    (async () => {
      try {
        const cameraPermission = await Camera.requestCameraPermissionsAsync();
        const foregroundPermission = await Location.requestForegroundPermissionsAsync();
        setHasPermission(cameraPermission.status === 'granted');
        setLocationPermission(foregroundPermission.status === 'granted');
      } catch {
        setHasPermission(false);
        setLocationPermission(false);
        setCameraError('Camera or location permissions could not be initialized on this device.');
      }
    })();
  }, []);

  React.useEffect(() => {
    if (!locationPermission || !autoDetectEnabled) {
      return undefined;
    }

    let isMounted = true;
    let locationSubscription;
    let accelerometerSubscription;

    const evaluateAutoReport = async (sample) => {
      const currentSpeedKmh = lastLocationRef.current?.speedKmh ?? 0;
      const zSamples = [...recentZValuesRef.current, sample.z];
      recentZValuesRef.current = zSamples.slice(-SENSOR_WINDOW_SIZE);

      const meanZ = recentZValuesRef.current.reduce((sum, value) => sum + value, 0) / recentZValuesRef.current.length;
      const zAxisChange = clampMagnitude(Math.abs(sample.z - meanZ) * 9.81);
      const variance = clampMagnitude(calculateVariance(recentZValuesRef.current) * 9.81);
      const isMoving = currentSpeedKmh >= AUTO_REPORT_MIN_SPEED_KMH;
      const isDemoShake = zAxisChange >= AUTO_REPORT_Z_THRESHOLD || variance >= AUTO_REPORT_MIN_VARIANCE;

      if (isMounted) {
        setMotionState({
          speedKmh: currentSpeedKmh,
          zAxisChange,
          variance,
          lastStatus: 'Demo mode active: slight shakes can trigger warning',
        });
      }

      const now = Date.now();
      const onCooldown = now - lastAutoSubmitRef.current < AUTO_REPORT_COOLDOWN_MS;
      if (onCooldown || !isDemoShake) {
        return;
      }

      try {
        const location = lastLocationRef.current;
        if (!location) return;

        lastAutoSubmitRef.current = now;
        if (isMounted) {
          showShakeNotice('warn', '⚠️ Pothole warning detected. Sending report...', true, 0);
        }
        await submitVibrationReport({
          latitude: location.latitude,
          longitude: location.longitude,
          peakAcceleration: Math.max(zAxisChange, variance),
          durationMs: 600,
          speedKmh: Math.max(currentSpeedKmh, DEMO_SEND_MIN_SPEED_KMH),
          zAxisChange,
          movementVariance: variance,
          moving: true,
        });

        if (isMounted) {
          showShakeNotice('success', '✅ Pothole warning sent to server.', false, 2400);
          setMotionState((prev) => ({
            ...prev,
            lastStatus: 'Auto-reported a strong moving z-axis spike',
          }));
        }
      } catch (error) {
        if (isMounted) {
          showShakeNotice('error', '❌ Pothole warning send failed. Will retry on next valid shake.', false, 3000);
          setMotionState((prev) => ({
            ...prev,
            lastStatus: 'Auto-detect saw a spike but report submission failed',
          }));
        }
      }
    };

    const startMonitoring = async () => {
      locationSubscription = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.Balanced,
          distanceInterval: 5,
          timeInterval: 3000,
        },
        (position) => {
          const speedMs = typeof position.coords.speed === 'number' && position.coords.speed > 0
            ? position.coords.speed
            : 0;
          lastLocationRef.current = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            speedKmh: speedMs * 3.6,
          };
        },
      );

      Accelerometer.setUpdateInterval(350);
      accelerometerSubscription = Accelerometer.addListener((sample) => {
        evaluateAutoReport(sample).catch(() => {
          if (isMounted) {
            setMotionState((prev) => ({
              ...prev,
              lastStatus: 'Auto-detection is temporarily unavailable.',
            }));
          }
        });
      });
    };

    startMonitoring().catch(() => {
      if (isMounted) {
        setMotionState((prev) => ({
          ...prev,
          lastStatus: 'Auto-detection unavailable on this device/session',
        }));
      }
    });

    return () => {
      isMounted = false;
      if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
      if (locationSubscription) locationSubscription.remove();
      if (accelerometerSubscription) accelerometerSubscription.remove();
    };
  }, [locationPermission, autoDetectEnabled]);

  const handleCapture = async () => {
    if (cameraRef.current) {
      const captured = await cameraRef.current.takePictureAsync();
      setPhoto(captured.uri);
    }
  };

  const submitVibrationReport = async ({
    latitude,
    longitude,
    peakAcceleration,
    durationMs,
    speedKmh,
    zAxisChange,
    movementVariance,
    moving,
  }) => {
    const formData = new FormData();
    const profile = await getStoredProfile();
    formData.append('latitude', String(latitude));
    formData.append('longitude', String(longitude));
    formData.append('peak_acceleration', String(peakAcceleration));
    formData.append('duration_ms', String(durationMs));
    formData.append('speed_kmh', String(speedKmh));
    formData.append('z_axis_change', String(zAxisChange));
    formData.append('movement_variance', String(movementVariance));
    formData.append('moving', moving ? 'true' : 'false');
    if (profile?.user_id) {
      formData.append('user_id', String(profile.user_id));
      formData.append('device_id', String(profile.user_id));
    }

    return api.post('/mobile/report/vibration', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      if (!photo) {
        Alert.alert('Error', 'Please capture a photo before submitting.');
        return;
      }
      if (!locationPermission) {
        Alert.alert('Location required', 'Allow location access to submit a visual report.');
        return;
      }

      const location = await Location.getCurrentPositionAsync({});
      const profile = await getStoredProfile();
      const formData = new FormData();
      formData.append('image', { uri: photo, name: 'pothole.jpg', type: 'image/jpeg' });
      formData.append('latitude', String(location.coords.latitude));
      formData.append('longitude', String(location.coords.longitude));
      formData.append('severity_estimate', 'Medium');
      formData.append('description', 'Mobile visual report');
      if (profile?.user_id) {
        formData.append('user_id', String(profile.user_id));
        formData.append('device_id', String(profile.user_id));
      }
      
      await api.post('/mobile/report/visual', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      Alert.alert('Success', 'Report submitted! 🎉');
      setPhoto(null);
    } catch (e) {
      Alert.alert('Error', e?.response?.data?.detail || 'Failed to submit report. Check API host and network connection.');
    } finally {
      setLoading(false);
    }
  };

  if (hasPermission === null) return <View style={styles.center}><Text>Requesting camera permission...</Text></View>;
  if (hasPermission === false) return <View style={styles.center}><Text>{cameraError || 'No camera permission'}</Text></View>;

  return (
    <View style={styles.container}>
      {shakeNotice.visible && (
        <View
          style={[
            styles.shakeBanner,
            shakeNotice.level === 'warn' && styles.shakeBannerWarn,
            shakeNotice.level === 'success' && styles.shakeBannerSuccess,
            shakeNotice.level === 'error' && styles.shakeBannerError,
          ]}
        >
          <Text style={styles.shakeBannerText}>{shakeNotice.message}</Text>
          {shakeNotice.sending ? <ActivityIndicator size="small" color="#fff" /> : null}
        </View>
      )}
      <View style={styles.autoCard}>
        <View style={styles.autoCardHeader}>
          <Text style={styles.autoCardTitle}>Auto z-axis detection</Text>
          <TouchableOpacity style={[styles.autoToggle, autoDetectEnabled ? styles.autoToggleOn : styles.autoToggleOff]} onPress={() => setAutoDetectEnabled((prev) => !prev)}>
            <Text style={styles.autoToggleText}>{autoDetectEnabled ? 'On' : 'Off'}</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.autoCardText}>Demo mode: even slight shakes can trigger warning + send attempt.</Text>
        <Text style={styles.autoMetric}>Speed: {motionState.speedKmh.toFixed(1)} km/h</Text>
        <Text style={styles.autoMetric}>Z change: {motionState.zAxisChange.toFixed(2)}</Text>
        <Text style={styles.autoMetric}>Motion variance: {motionState.variance.toFixed(2)}</Text>
        <Text style={styles.autoMetric}>API: {getApiBaseUrl()}</Text>
        <Text style={styles.autoHint}>{motionState.lastStatus}</Text>
      </View>
      {!photo ? (
        <>
          <Camera style={styles.camera} type={type} ref={cameraRef}>
            <View style={styles.cameraButtons}>
              <TouchableOpacity onPress={() => setType(type === backType ? frontType : backType)}>
                <Text style={styles.buttonText}>Flip</Text>
              </TouchableOpacity>
            </View>
          </Camera>
          <TouchableOpacity style={styles.captureButton} onPress={handleCapture}>
            <Text style={styles.captureText}>📸</Text>
          </TouchableOpacity>
        </>
      ) : (
        <>
          <Image source={{ uri: photo }} style={styles.previewImage} />
          <View style={styles.buttonGroup}>
            <TouchableOpacity style={[styles.button, styles.retakeButton]} onPress={() => setPhoto(null)}>
              <Text style={styles.buttonText}>Retake</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.button, styles.submitButton]}
              onPress={handleSubmit}
              disabled={loading}
            >
              {loading ? <ActivityIndicator color="white" /> : <Text style={styles.buttonText}>Submit Report</Text>}
            </TouchableOpacity>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  shakeBanner: {
    position: 'absolute',
    top: 48,
    left: 12,
    right: 12,
    zIndex: 20,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  shakeBannerWarn: { backgroundColor: '#b45309' },
  shakeBannerSuccess: { backgroundColor: '#15803d' },
  shakeBannerError: { backgroundColor: '#b91c1c' },
  shakeBannerText: { color: '#fff', fontWeight: '700', fontSize: 12, flex: 1, marginRight: 8 },
  autoCard: { backgroundColor: '#111827', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#1f2937' },
  autoCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  autoCardTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  autoCardText: { color: '#d1d5db', fontSize: 13, marginBottom: 8 },
  autoMetric: { color: '#e5e7eb', fontSize: 12, marginBottom: 2 },
  autoHint: { color: '#93c5fd', fontSize: 12, marginTop: 6 },
  autoToggle: { borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 },
  autoToggleOn: { backgroundColor: '#2563eb' },
  autoToggleOff: { backgroundColor: '#4b5563' },
  autoToggleText: { color: '#fff', fontWeight: '700' },
  camera: { flex: 1 },
  cameraButtons: { flex: 1, justifyContent: 'space-around', paddingHorizontal: 20 },
  captureButton: { alignSelf: 'center', width: 80, height: 80, borderRadius: 40, backgroundColor: '#3b82f6', justifyContent: 'center', alignItems: 'center', marginBottom: 20 },
  captureText: { fontSize: 40 },
  previewImage: { flex: 1 },
  buttonGroup: { flexDirection: 'row', padding: 20, gap: 10, backgroundColor: '#fff' },
  button: { flex: 1, padding: 16, borderRadius: 8, justifyContent: 'center', alignItems: 'center' },
  retakeButton: { backgroundColor: '#ef4444' },
  submitButton: { backgroundColor: '#22c55e' },
  buttonText: { fontSize: 16, fontWeight: 'bold', color: '#fff' },
});
