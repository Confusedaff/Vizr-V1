import { BrowserRouter, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./components/RequireAuth";
import { AuthProvider } from "./hooks/useAuth";
import { AuthPage } from "./pages/AuthPage";
import { Dashboard } from "./pages/Dashboard";
import { EmptyState } from "./pages/EmptyState";
import { JobDetail } from "./pages/JobDetail";
import { LandingPage } from "./pages/LandingPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<AuthPage />} />
          <Route
            path="/app"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          >
            <Route index element={<EmptyState />} />
            <Route path="jobs/:jobId" element={<JobDetail />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
