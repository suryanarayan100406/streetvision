import React, { useState, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Image, Alert } from 'react-native';
import { Camera } from 'expo-camera';
import * as Location from 'expo-location';
import api from '../api';

export default function ReportScreen() {
  const [hasPermission, setHasPermission] = useState(null);
  const [type, setType] = useState(Camera.Constants.Type.back);
  const [photo, setPhoto] = useState(null);
  const [loading, setLoading] = useState(false);
  const cameraRef = useRef(null);

  React.useEffect(() => {
    (async () => {
      const { status } = await Camera.requestCameraPermissionsAsync();
      setHasPermission(status === 'granted');
    })();
  }, []);

  const handleCapture = async () => {
    if (cameraRef.current) {
      const captured = await cameraRef.current.takePictureAsync();
      setPhoto(captured.uri);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const location = await Location.getCurrentPositionAsync({});
      const formData = new FormData();
      formData.append('photo', { uri: photo, name: 'pothole.jpg', type: 'image/jpeg' });
      formData.append('latitude', location.coords.latitude);
      formData.append('longitude', location.coords.longitude);
      
      await api.post('/mobile/report', formData);
      Alert.alert('Success', 'Report submitted! 🎉');
      setPhoto(null);
    } catch (e) {
      Alert.alert('Error', 'Failed to submit report');
    } finally {
      setLoading(false);
    }
  };

  if (hasPermission === null) return <View style={styles.center}><Text>Requesting camera permission...</Text></View>;
  if (hasPermission === false) return <View style={styles.center}><Text>No camera permission</Text></View>;

  return (
    <View style={styles.container}>
      {!photo ? (
        <>
          <Camera style={styles.camera} type={type} ref={cameraRef}>
            <View style={styles.cameraButtons}>
              <TouchableOpacity onPress={() => setType(type === Camera.Constants.Type.back ? Camera.Constants.Type.front : Camera.Constants.Type.back)}>
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
