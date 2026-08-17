import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router";
import { AppShell } from "./layouts/AppShell";
import { HomePage } from "./pages/HomePage";
import { SessionPage } from "./pages/SessionPage";

const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="sessions/:sessionId" element={<SessionPage />} />
          <Route
            path="sessions/:sessionId/dashboard"
            element={
              <Suspense fallback={<div className="grid min-h-dvh place-items-center text-sm text-steel">Loading dashboard...</div>}>
                <DashboardPage />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
