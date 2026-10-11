import { lazy } from "react";
import { Navigate, type RouteObject } from "react-router-dom";

/** One lazy chunk per page. Vite can only split these if the import()
 *  argument is a static literal — a computed path silently bundles
 *  everything. */
const MyLeavePage = lazy(() => import("./pages/MyLeavePage"));
const ApplyPage = lazy(() => import("./pages/ApplyPage"));
const BalancesPage = lazy(() => import("./pages/BalancesPage"));
const NotificationsPage = lazy(
  () => import("./pages/NotificationsPage"));
const QueuePage = lazy(() => import("./pages/QueuePage"));
const SanctionsPage = lazy(() => import("./pages/SanctionsPage"));
const PolicyPage = lazy(() => import("./pages/PolicyPage"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));

/** Paths are RELATIVE — the shell mounts them under the manifest's
 *  basePath.
 *
 *  Every entry here has a matching nav item in the server's registry.py,
 *  and that correspondence matters: the sidebar is built server-side, so a
 *  nav item without a route here renders a link that goes nowhere. */
export const routes: RouteObject[] = [
  { index: true, element: <Navigate to="mine" replace /> },
  { path: "mine", element: <MyLeavePage /> },
  { path: "apply", element: <ApplyPage /> },
  { path: "balances", element: <BalancesPage /> },
  { path: "notifications", element: <NotificationsPage /> },
  { path: "queue", element: <QueuePage /> },
  { path: "sanctions", element: <SanctionsPage /> },
  { path: "policy", element: <PolicyPage /> },
  { path: "calendar", element: <CalendarPage /> },
  { path: "reports", element: <ReportsPage /> },
];