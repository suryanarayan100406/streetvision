import { useState, useEffect } from 'react';
import { io } from 'socket.io-client';

const socketUrl =
  import.meta.env.VITE_SOCKET_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000/dashboard-stream`;

const socket = io(socketUrl, {
  transports: ['websocket', 'polling'],
});

export default function useSocket(channel) {
  const [data, setData] = useState(null);

  useEffect(() => {
    socket.on(channel, setData);
    return () => socket.off(channel);
  }, [channel]);

  return data;
}
