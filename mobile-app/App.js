import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';

import MapScreen from './src/screens/MapScreen';
import ReportScreen from './src/screens/ReportScreen';
import LeaderboardScreen from './src/screens/LeaderboardScreen';
import ProfileScreen from './src/screens/ProfileScreen';

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused, color, size }) => {
            let iconName;
            if (route.name === 'Map') iconName = focused ? 'map' : 'map-outline';
            else if (route.name === 'Report') iconName = focused ? 'camera' : 'camera-outline';
            else if (route.name === 'Leaderboard') iconName = focused ? 'podium' : 'podium-outline';
            else if (route.name === 'Profile') iconName = focused ? 'person' : 'person-outline';
            return <Ionicons name={iconName} size={size} color={color} />;
          },
          tabBarActiveTintColor: '#3b82f6',
          tabBarInactiveTintColor: '#9ca3af',
          headerShown: true,
        })}
      >
        <Tab.Screen name="Map" component={MapScreen} />
        <Tab.Screen name="Report" component={ReportScreen} />
        <Tab.Screen name="Leaderboard" component={LeaderboardScreen} />
        <Tab.Screen name="Profile" component={ProfileScreen} />
      </Tab.Navigator>
      <StatusBar barStyle="dark-content" />
    </NavigationContainer>
  );
}
