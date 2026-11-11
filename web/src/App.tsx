import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthContext";
import LoginPage from "./pages/LoginPage";
import CitizenLayout from "./pages/citizen/CitizenLayout";
import AdminLayout from "./pages/admin/AdminLayout";

function Guard({ role, children }: { role: "citizen" | "admin"; children: React.ReactNode }) {
  const auth = useAuth();
  if (!auth.token) return <Navigate to="/login" replace />;
  if (auth.role !== role) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RootRedirect() {
  const auth = useAuth();
  if (!auth.token) return <Navigate to="/login" replace />;
  if (auth.role === "admin") return <Navigate to="/admin/overview" replace />;
  return <Navigate to="/app/chat" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<RootRedirect />} />
        <Route path="/app/*" element={
          <Guard role="citizen"><CitizenLayout /></Guard>
        } />
        <Route path="/admin/*" element={
          <Guard role="admin"><AdminLayout /></Guard>
        } />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
