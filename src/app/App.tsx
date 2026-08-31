import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import { ThemeProvider } from "../context/ThemeContext";
import { StudySessionProvider } from "../context/StudySessionContext";
import { PomodoroProvider } from "../context/PomodoroContext";
import { AuthProvider } from "../context/AuthContext";
import { AppShell } from "../layout/AppShell";
import { HomePage } from "../pages/HomePage";
import AdminPanelPage from "../pages/admin/AdminPanelPage";
import { ProfilePage } from "../pages/ProfilePage";
import ThemeSettingsPage from "../pages/settings/ThemeSettingsPage";
import SettingsHubPage from "../pages/settings/SettingsHubPage";
import AiControlCenterPage from "../pages/settings/AiControlCenterPage";
import { PluginSettingsPage } from "../pages/settings/PluginSettingsPage";
import { AddWordsPage } from "../pages/vocab/AddWordsPage";
import { AiCoachPage } from "../pages/AiCoachPage";
import { HubCortexPage } from "../pages/HubCortexPage";
import { ProjectAgentPage } from "../pages/ProjectAgentPage";
import { JournalPage } from "../pages/JournalPage";

// Import registry and trigger registration of all plugins
import "../plugins"; 
import { PluginRegistryProvider, usePlugins } from "../plugins/registry";
import { FeatureStudioPage } from "../pages/settings/FeatureStudioPage";
import { EasterProvider } from "../easter";
import { AppErrorBoundary } from "../components/layout/AppErrorBoundary";

function AppRoutes() {
  const { getRoutes, isLoaded } = usePlugins();
  
  if (!isLoaded) return <div className="h-screen w-screen flex items-center justify-center">Loading modules...</div>;

  const pluginRoutes = getRoutes();

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="login" element={<Navigate to="/profile" replace />} />
        <Route path="admin" element={<AdminPanelPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="settings" element={<SettingsHubPage />} />
        <Route path="settings/ai" element={<AiControlCenterPage />} />
        <Route path="settings/theme" element={<ThemeSettingsPage />} />
        <Route path="settings/plugins" element={<PluginSettingsPage />} />
        <Route path="settings/features" element={<FeatureStudioPage />} />
        <Route path="gre-vocab/add-words" element={<AddWordsPage />} />
        <Route path="hub" element={<HubCortexPage />} />
        <Route path="ai-coach" element={<AiCoachPage />} />
        <Route path="project-agent" element={<ProjectAgentPage />} />
        <Route path="journal" element={<JournalPage />} />

        {/* Dynamically mount plugin routes */}
        {pluginRoutes.map((route, i) => (
          <Route key={i} path={route.path} element={route.element} />
        ))}

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
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
      <AuthProvider>
        <EasterProvider>
        <PluginRegistryProvider>
          <PomodoroProvider>
            <StudySessionProvider>
              <BrowserRouter>
                <DynamicProviders>
                  <AppErrorBoundary>
                    <AppRoutes />
                  </AppErrorBoundary>
                </DynamicProviders>
              </BrowserRouter>
            </StudySessionProvider>
          </PomodoroProvider>
        </PluginRegistryProvider>
        </EasterProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
