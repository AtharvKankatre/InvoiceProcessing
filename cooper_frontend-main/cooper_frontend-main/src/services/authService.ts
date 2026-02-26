import { apiService } from './apiService';
import type { LoginCredentials, AuthResponse } from './apiService';

interface TokenPayload {
  exp: number;
  user_id: string;
  username: string;
}

class AuthService {
  private refreshPromise: Promise<AuthResponse> | null = null;

  /**
   * Login user
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    try {
      const response = await apiService.login(credentials);
      // Validate tokens after login
      this.validateTokens(response.access, response.refresh);
      return response;
    } catch (error) {
      // Clear any existing tokens on login failure
      this.clearAuth();
      throw error;
    }
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    try {
      await apiService.logout();
    } catch (error) {
      console.error('Logout API call failed:', error);
      // Continue with local cleanup even if API call fails
    } finally {
      this.clearAuth();
      this.refreshPromise = null;
    }
  }

  /**
   * Refresh authentication token with singleton pattern to prevent race conditions
   */
  async refreshToken(): Promise<AuthResponse> {
    // If there's already a refresh in progress, return that promise
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    // Create new refresh promise
    this.refreshPromise = this.performTokenRefresh();
    
    try {
      const result = await this.refreshPromise;
      return result;
    } finally {
      // Clear the promise after completion (success or failure)
      this.refreshPromise = null;
    }
  }

  /**
   * Perform the actual token refresh
   */
  private async performTokenRefresh(): Promise<AuthResponse> {
    const refreshToken = this.getRefreshToken();
    
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    if (this.isTokenExpired(refreshToken)) {
      this.clearAuth();
      throw new Error('Refresh token expired');
    }

    try {
      const response = await apiService.refreshToken();
      this.validateTokens(response.access, response.refresh);
      return response;
    } catch {
      // If refresh fails, clear all auth data
      this.clearAuth();
      throw new Error('Token refresh failed');
    }
  }

  /**
   * Get stored access token
   */
  getAccessToken(): string | null {
    return localStorage.getItem('access_token');
  }

  /**
   * Get stored refresh token
   */
  getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  /**
   * Check if user is authenticated with proper token validation
   */
  isAuthenticated(): boolean {
    const accessToken = this.getAccessToken();
    const refreshToken = this.getRefreshToken();

    // Must have both tokens
    if (!accessToken || !refreshToken) {
      return false;
    }

    // Check if refresh token is expired
    if (this.isTokenExpired(refreshToken)) {
      this.clearAuth();
      return false;
    }

    // If access token is expired but refresh token is valid, we're still authenticated
    // The API calls will handle refreshing the access token automatically
    return true;
  }

  /**
   * Check if access token needs refresh
   */
  isAccessTokenExpired(): boolean {
    const accessToken = this.getAccessToken();
    if (!accessToken) return true;
    return this.isTokenExpired(accessToken);
  }

  /**
   * Check if a token is expired
   */
  private isTokenExpired(token: string): boolean {
    try {
      const payload = this.decodeToken(token);
      const currentTime = Math.floor(Date.now() / 1000);
      // Add 30 second buffer to account for clock skew
      return payload.exp <= (currentTime + 30);
    } catch {
      return true; // Treat invalid tokens as expired
    }
  }

  /**
   * Decode JWT token payload
   */
  private decodeToken(token: string): TokenPayload {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch {
      throw new Error('Invalid token format');
    }
  }

  /**
   * Validate token format and structure
   */
  private validateTokens(accessToken: string, refreshToken: string): void {
    try {
      this.decodeToken(accessToken);
      this.decodeToken(refreshToken);
    } catch {
      throw new Error('Invalid token format received from server');
    }
  }

  /**
   * Get user information from access token
   */
  getUserInfo(): { userId: string; username: string } | null {
    const accessToken = this.getAccessToken();
    if (!accessToken) return null;

    try {
      const payload = this.decodeToken(accessToken);
      return {
        userId: payload.user_id,
        username: payload.username
      };
    } catch (error) {
      console.error('Error getting user info:', error);
      return null;
    }
  }

  /**
   * Clear all stored auth data
   */
  clearAuth(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    this.refreshPromise = null;
  }

  /**
   * Force logout and redirect to login
   */
  forceLogout(): void {
    this.clearAuth();
    // Redirect to login page
    window.location.href = '/';
  }
}

export const authService = new AuthService();
export default authService; 