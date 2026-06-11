import { HashRouter, Routes, Route, Outlet } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import AdminPage from "./pages/AdminPage";
import SecurityPage from "./pages/SecurityPage";
import UsersPage from './pages/UsersPage';
import AuditLogsPage from './pages/AuditLogsPage';
import ViewLogsPage from './pages/ViewLogsPage';
import UserProfilePage from "./pages/UserProfilePage";
import PoliciesPage from "./pages/PoliciesPage";
import { WebSocketProvider } from './context/WebSocketContext';


const PrivateRoutes = () => {
  return (
    <WebSocketProvider>
      <Outlet />
    </WebSocketProvider>
  );
};

export default function App() {
  return (
    <div className="min-h-screen bg-background min-w-[360px]">
      <HashRouter>
        <WebSocketProvider>
          <Routes>
            <Route path="/" element={<LoginPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route element={<PrivateRoutes />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/security" element={<SecurityPage />} />
                <Route path="/users" element={<UsersPage />} />
                <Route path="/audit-logs" element={<AuditLogsPage />} />
                <Route path="/view-logs" element={<ViewLogsPage />} />
                <Route path="/profile" element={<UserProfilePage />} />
                <Route path="/user/:id" element={<UserProfilePage />} />
                <Route path="/policies" element={<PoliciesPage />} />
            </Route>

            {/* Catch-all route for unmatched paths */}
            <Route path="*" element={<LoginPage />} />
          </Routes>
        </WebSocketProvider>
      </HashRouter>
    </div>
  );
}
