// src/contexts/AuthContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { setCurrentUser } from '../services/api';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Update user state and API client
  const updateUser = (userData) => {
    setUser(userData);
    setCurrentUser(userData); // Update the API client's user reference
  };

  // For now, simulate authentication with test user
  useEffect(() => {
    // TODO: Implement real authentication
    const testUser = { 
      id: 'test-user-123', 
      full_name: 'Test User',
      email: 'test@example.com'
    };
    
    updateUser(testUser);
    setLoading(false);
  }, []);

  const login = (userData) => {
    updateUser(userData);
  };

  const logout = () => {
    updateUser(null);
  };

  return (
    <AuthContext.Provider value={{ 
      user, 
      setUser: updateUser, 
      loading,
      login,
      logout 
    }}>
      {children}
    </AuthContext.Provider>
  );
};