# Project Structure

This React TypeScript project follows industry-standard folder organization:

## Directory Structure

```
src/
├── components/     # Reusable UI components
├── pages/         # Page-level components (routes)
├── services/      # API calls and business logic
├── hooks/         # Custom React hooks
├── utils/         # Utility functions and helpers
├── types/         # TypeScript type definitions
├── contexts/      # React context providers
├── assets/        # Static assets (images, icons, etc.)
└── lib/           # Third-party library configurations
```

## Key Features

### 1. Login Page (`src/pages/LoginPage.tsx`)
- Modern, responsive login form
- Username and password fields
- Loading states and form validation
- Beautiful gradient background and animations

### 2. Authentication Service (`src/services/authService.ts`)
- Handles login/logout operations
- Token management with localStorage
- User session management
- API integration ready

### 3. Type Definitions (`src/types/auth.ts`)
- TypeScript interfaces for authentication
- User data structures
- API response types

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Open your browser to the displayed URL (usually `http://localhost:5173`)

## Development Guidelines

- **Components**: Place reusable UI components in `src/components/`
- **Pages**: Place route-level components in `src/pages/`
- **Services**: Place API calls and business logic in `src/services/`
- **Types**: Define TypeScript interfaces in `src/types/`
- **Hooks**: Create custom React hooks in `src/hooks/`
- **Utils**: Place helper functions in `src/utils/`

## Next Steps

1. Implement actual authentication API endpoints
2. Add routing with React Router
3. Create protected routes
4. Add error handling and notifications
5. Implement user registration
6. Add form validation libraries if needed 