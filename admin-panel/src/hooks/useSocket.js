import { useEffect, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';

const SOCKET_URL = '/ws';

export function useSocket(namespace = '/admin-stream', channels = []) {
  const socketRef = useRef(null);
  const listenersRef = useRef({});

  useEffect(() => {
    socketRef.current = io(`${SOCKET_URL}${namespace}`, {
      path: '/socket.io',
      transports: ['websocket'],
    });

    socketRef.current.on('connect', () => {
      if (channels.length > 0) {
        socketRef.current.emit('subscribe', { channels });
      }
    });

    return () => {
      socketRef.current?.disconnect();
    };
  }, [namespace, channels.join(',')]);

  const on = useCallback((event, handler) => {
    socketRef.current?.on(event, handler);
    listenersRef.current[event] = handler;
  }, []);

  const off = useCallback((event) => {
    if (listenersRef.current[event]) {
      socketRef.current?.off(event, listenersRef.current[event]);
      delete listenersRef.current[event];
    }
  }, []);

  return { on, off, socket: socketRef };
}
