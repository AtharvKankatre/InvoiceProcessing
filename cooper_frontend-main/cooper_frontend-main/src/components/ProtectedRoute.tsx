import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { authService } from '@/services/authService';
import Loading from '@/components/ui/loading';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    const checkAuthentication = async () => {
      try {
        setIsLoading(true);
        
        // Check if user is authenticated
        const authenticated = authService.isAuthenticated();
        
        if (authenticated) {
          // If access token is expired but refresh token is valid, try to refresh
          if (authService.isAccessTokenExpired()) {
            try {
              await authService.refreshToken();
              setIsAuthenticated(true);
            } catch (error) {
              console.error('Token refresh failed:', error);
              setIsAuthenticated(false);
            }
          } else {
            setIsAuthenticated(true);
          }
        } else {
          setIsAuthenticated(false);
        }
      } catch (error) {
        console.error('Authentication check failed:', error);
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuthentication();
  }, [location.pathname]);

  // Show loading while checking authentication
  if (isLoading) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Loading message="Checking authentication..." minHeight="200px" />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/" replace state={{ from: location }} />;
  }

  // Render the protected component
  return <>{children}</>;
};

export default ProtectedRoute; 