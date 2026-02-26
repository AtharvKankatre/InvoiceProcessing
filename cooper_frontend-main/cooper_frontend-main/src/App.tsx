import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import BalanceHistoryPage from './pages/BalanceHistoryPage';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import InvoiceDetailsPage from './pages/InvoiceDetailsPage';
import UploadInvoicesPage from './pages/UploadInvoicesPage';
import ReconciliationsPage from './pages/ReconciliationsPage';
import PartReconciliationsPage from './pages/PartReconciliationsPage';
import InputtedEntriesPage from './pages/InputtedEntriesPage';
import ThreeContainerPage from './pages/ThreeContainerPage';
import PartHistoryPage from './pages/PartHistoryPage';
import ProtectedRoute from './components/ProtectedRoute';
import AuthErrorHandler from './components/AuthErrorHandler';
import './App.css';

const PageWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => <>{children}</>;

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <Routes location={location} key={location.pathname}>
      <Route path="/" element={<PageWrapper><LoginPage /></PageWrapper>} />
      <Route path="/dashboard" element={<ProtectedRoute><PageWrapper><DashboardPage /></PageWrapper></ProtectedRoute>} />
      <Route path="/invoice-details" element={<ProtectedRoute><PageWrapper><InvoiceDetailsPage /></PageWrapper></ProtectedRoute>} />
      <Route path="/upload-invoices" element={<ProtectedRoute><PageWrapper><UploadInvoicesPage /></PageWrapper></ProtectedRoute>} />
      <Route path="/reconciliations" element={<ProtectedRoute><PageWrapper><ReconciliationsPage /></PageWrapper></ProtectedRoute>} />
      <Route path="/part-reconciliations" element={<ProtectedRoute><PageWrapper><PartReconciliationsPage /></PageWrapper></ProtectedRoute>} />
      <Route path="/inputted-entries" element={<ProtectedRoute><PageWrapper><InputtedEntriesPage /></PageWrapper></ProtectedRoute>} />
      <Route path="/three-container" element={<ProtectedRoute><PageWrapper><ThreeContainerPage /></PageWrapper></ProtectedRoute>} />
      <Route path="/balance-history" element={<ProtectedRoute><PageWrapper><BalanceHistoryPage /></PageWrapper></ProtectedRoute>} />
      <Route path="/part-history" element={<ProtectedRoute><PageWrapper><PartHistoryPage /></PageWrapper></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <Router>
      <AuthErrorHandler>
        <div className="App" style={{ height: '100%' }}>
          <AnimatedRoutes />
        </div>
      </AuthErrorHandler>
    </Router>
  );
}

export default App;
