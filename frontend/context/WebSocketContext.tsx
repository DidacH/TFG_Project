import React, { createContext, useContext, useEffect, useState } from 'react';
import { io, Socket } from 'socket.io-client';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000';

// Define the context type
interface WebSocketContextType {
  socket: Socket | null;
}

const WebSocketContext = createContext<WebSocketContextType>({ socket: null });

// Hook to use the WebSocket context in any component
export const useWebSocket = () => useContext(WebSocketContext);

export const WebSocketProvider = ({ children }: { children: React.ReactNode }) => {
  const [socket, setSocket] = useState<Socket | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('token');

    // Only connect if we have a token and no existing socket connection
    if (token && !socket) {
      console.log("🔌 Initializing global WebSocket connection...");
      
      const newSocket = io(API_URL, {
        transports: ['websocket'],
        withCredentials: true,
        // Opcional: Pots enviar el token en l'auth del socket si el backend ho requereix
        // auth: { token } 
      });

      newSocket.on("connect", () => {
        console.log("🟢 Global Websocket connected. ID:", newSocket.id);
      });

      setSocket(newSocket);

      // Cleanup function to disconnect the socket when the component unmounts
      return () => {
        console.log("🔴 Closing global WebSocket connection...");
        newSocket.disconnect();
      };
    }
  }, []);

  return (
    <WebSocketContext.Provider value={{ socket }}>
      {children}
    </WebSocketContext.Provider>
  );
};