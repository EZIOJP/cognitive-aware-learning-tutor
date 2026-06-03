import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import { ThemeProvider } from "../context/ThemeContext";
import { StudySessionProvider } from "../context/StudySessionContext";
import { AuthProvider } from "../context/AuthContext";
import { AppShell } from "../layout/AppShell";
import { HomePage } from "../pages/HomePage";
import LoginPage from "../pages/auth/LoginPage";
import AdminPanelPage from "../pages/admin/AdminPanelPage";
import { ProfilePage } from "../pages/ProfilePage";
import ThemeSettingsPage from "../pages/settings/ThemeSettingsPage";
import SettingsHubPage from "../pages/settings/SettingsHubPage";
import { PluginSettingsPage } from "../pages/settings/PluginSettingsPage";
import { AddWordsPage } from "../pages/vocab/AddWordsPage";

// Import registry and trigger registration of all plugins
import "../plugins"; 
import { usePlugins } from "../plugins/registry";

function AppRoutes() {
  const { getRoutes, isLoaded } = usePlugins();
  
  if (!isLoaded) return <div className="h-screen w-screen flex items-center justify-center">Loading modules...</div>;

  const pluginRoutes = getRoutes();

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="admin" element={<AdminPanelPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="settings" element={<SettingsHubPage />} />
          <Route path="settings/theme" element={<ThemeSettingsPage />} />
          <Route path="settings/plugins" element={<PluginSettingsPage />} />
          <Route path="gre-vocab/add-words" element={<AddWordsPage />} />
          
          {/* Dynamically mount plugin routes */}
          {pluginRoutes.map((route, i) => (
            <Route key={i} path={route.path} element={route.element} />
          ))}

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function DynamicProviders({ children }: { children: React.ReactNode }) {
  const { getProviders, isLoaded } = usePlugins();
  
  if (!isLoaded) return <>{children}</>;

  const providers = getProviders() as Array<({ children }: { children: React.ReactNode }) => React.ReactNode>;
  
  // Wrap children in each active provider (outermost = first in list)
  return providers.reduceRight(
    (acc: React.ReactNode, Provider) => <Provider>{acc}</Provider>,
    children
  ) as React.ReactElement;
}

export default function App() {
  return (
    <ThemeProvider>
      <StudySessionProvider>
        <AuthProvider>
          <DynamicProviders>
            <AppRoutes />
          </DynamicProviders>
        </AuthProvider>
      </StudySessionProvider>
    </ThemeProvider>
  );
}
