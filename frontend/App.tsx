import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/RegisterPage";

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <HashRouter>
        <Routes>
          <Route path="/" element={<LoginPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/home" element={<HomePage />} />
          {/* Catch-all route for unmatched paths */}
          <Route path="*" element={<LoginPage />} />
        </Routes>
      </HashRouter>
    </div>
  );
}
