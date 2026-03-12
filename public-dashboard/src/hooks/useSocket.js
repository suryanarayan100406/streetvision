import { useState, useEffect } from 'react';
import { io } from 'socket.io-client';

const socket = io('http://localhost:8000/dashboard-stream', {
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
