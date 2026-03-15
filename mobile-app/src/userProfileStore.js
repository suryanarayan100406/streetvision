import AsyncStorage from '@react-native-async-storage/async-storage';

const PROFILE_KEY = 'cg_pothole_user_profile_v1';

export async function getStoredProfile() {
  try {
    const raw = await AsyncStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.user_id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export async function setStoredProfile(profile) {
  if (!profile?.user_id) return;
  await AsyncStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

export async function clearStoredProfile() {
  await AsyncStorage.removeItem(PROFILE_KEY);
}
