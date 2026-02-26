import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '@/services/authService';

interface AuthErrorHandlerProps {
  children: React.ReactNode;
}

const AuthErrorHandler: React.FC<AuthErrorHandlerProps> = ({ children }) => {
  const navigate = useNavigate();

  useEffect(() => {
    // Listen for authentication errors
    const handleAuthError = (event: CustomEvent) => {
      console.error('Authentication error detected:', event.detail);
      
      // Clear auth data and redirect to login
      authService.clearAuth();
      navigate('/', { replace: true });
    };

    // Listen for storage changes (e.g., logout in another tab)
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'access_token' && event.newValue === null) {
        // Token was removed, redirect to login
        navigate('/', { replace: true });
      }
    };

    // Add event listeners
    window.addEventListener('auth-error', handleAuthError as EventListener);
    window.addEventListener('storage', handleStorageChange);

    // Cleanup
    return () => {
      window.removeEventListener('auth-error', handleAuthError as EventListener);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [navigate]);

  return <>{children}</>;
};

// Utility function to dispatch auth errors
export const dispatchAuthError = (error: string) => {
  const event = new CustomEvent('auth-error', {
    detail: { message: error, timestamp: new Date().toISOString() }
  });
  window.dispatchEvent(event);
};

export default AuthErrorHandler; 