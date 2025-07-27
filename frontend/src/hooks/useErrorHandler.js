// src/hooks/useErrorHandler.js
import { useState } from 'react';

export const useErrorHandler = () => {
  const [error, setError] = useState(null);

  const handleError = (error) => {
    console.error('API Error:', error);
    setError(error.response?.data?.detail || 'An unexpected error occurred');
  };

  const clearError = () => setError(null);

  return { error, handleError, clearError };
};