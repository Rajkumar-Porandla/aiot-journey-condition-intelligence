## 2026-11-06T11:21:50Z

You are teamwork_worker_frontend, an implementation worker.
Working directory: /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/teamwork_worker_frontend
Original request path: /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/ORIGINAL_REQUEST.md
Scope document: /Users/porandlarajkumar/Documents/IOT/PROJECT.md
Survey findings path: /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/teamwork_explorer_survey_2/handoff.md

MANDATORY FIRST STEP: Read /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/ORIGINAL_REQUEST.md completely.
Also read /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/teamwork_explorer_survey_2/handoff.md.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write ownership:
You exclusively own and may modify files under:
- frontend/src/
- frontend/index.html
- frontend/package.json

Your mission: Implement Milestone 3 (Frontend Defect Remediation & UI Features):
1. Module 2 Shipment Management:
   - Add Shipment Edit capability: add an "Edit" button to `ShipmentsPage.jsx` table actions, create a modal or inline form allowing updating `carrier`, `notes`, and `expected_delivery_time`, calling `api.updateShipment(id, data)` and refreshing the table on success.
   - Replace native `window.confirm()` in `ShipmentsPage.jsx` with an in-app styled confirmation modal (Apple-style frosted glass / dialog with Confirm Delete and Cancel buttons).
   - Add a Shipment Details modal or drawer: when clicking shipment ID/code, allow inspecting static details (origin/dest coordinates, timestamps, profile safe bounds, carrier, notes) with a direct button to "Open Live Monitoring".
2. Module 7 What-If Simulator:
   - In `WhatIfPage.jsx`, add the missing Humidity Exposure Duration slider for `humExpHours` (range: 0h to `journeyDuration`h, step 0.5h).
   - Fix TDZ variable ordering: ensure `runSimulation` is defined before any `useEffect` referencing it.
3. Module 3 Leaflet Map in `MonitoringPage.jsx`:
   - Fix circle marker stacking / memory leak: use a Leaflet `LayerGroup` (or clear existing markers) before adding origin/destination/waypoint markers on telemetry poll.
   - Fix React unmount cleanup: ensure `return () => { map.remove(); }` properly cleans up map instance on component unmount or shipment switch.
   - Fix map bounds: re-center / fitBounds when the user changes shipments from the dropdown.
4. Module 1 Executive Dashboard in `DashboardPage.jsx`:
   - Add aggregated Temperature & Humidity Monitoring KPI cards (e.g. Fleet Telemetry Live Status, Average Cold-Chain Temperature with compliance indicator, Average Humidity with compliance indicator).
5. Role-Based UI Gating (RBAC in UI):
   - In `ShipmentsPage.jsx`: Only admins can see and use the Delete Shipment button (`isAdmin` from `useAuth()`). For operators, either hide delete button or show a tooltip/disabled badge.
   - In `ProductsPage.jsx`: Gate Create / Update Product Profile form. If `!isAdmin`, display a clean "Operator Mode: View-Only (Admin role required to modify profiles)" banner and disable form submit buttons.
6. Module 8 Compare Page & Module 9 Reports Page:
   - In `ComparePage.jsx`: Use `comparing` state to render a loading spinner during API request and disable selection checkboxes while comparing.
   - In `ReportsPage.jsx`: Add loading feedback and error handling during PDF generation / download. Handle errors gracefully if fetching shipments fails.
7. Code Hygiene & Polish:
   - Update `frontend/index.html` title to `<title>AIoT Journey Condition Intelligence</title>`.
   - Remove unused dead boilerplate `frontend/src/App.css`.
   - Resolve `oxlint` warnings across frontend files.
   - Run `npm run lint` and `npm run build` in `frontend/` to verify zero errors and clean build.

Deliver your handoff in /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/teamwork_worker_frontend/handoff.md documenting all modified files, features added, and build/lint output. When done, send a message to your caller.
