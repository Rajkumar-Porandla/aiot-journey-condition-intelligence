# Frontend Architecture & UI Workflow Survey Report

## 1. Observation

### 1.1 Frontend Structure, Dependencies & Build Health
- **Location**: `/Users/porandlarajkumar/Documents/IOT/frontend`
- **Dependencies** (`frontend/package.json`):
  - `react`: `^19.3.1`, `react-dom`: `^19.3.1`
  - `react-router-dom`: `^7.18.5`
  - `chart.js`: `^4.6.1`, `react-chartjs-2`: `^5.3.1`
  - `leaflet`: `^1.9.4`
  - Dev dependencies: `vite`: `^8.3.6`, `@vitejs/plugin-react`: `^6.1.2`, `oxlint`: `^1.90.0`
- **Vite Configuration** (`frontend/vite.config.js`):
  - Port 5173 with proxy rule: `/api` -> `http://127.0.0.1:5001`.
- **Build Execution** (`npm run build`):
  - Exited with code 0 (`✓ built in 126ms`). Chunks generated: `dist/assets/index-k-PMd3Yh.css` (24.87 kB) and `dist/assets/index-BC_MZD-i.js` (682.48 kB).
- **Linter Execution** (`npm run lint` / `oxlint`):
  - 20 warnings, 0 errors across 19 files.
  - Key warnings observed:
    - `src/pages/WhatIfPage.jsx:69:9`: `react(immutability)`: Cannot access variable while it is being initialized (`runSimulation` is invoked inside `useEffect` before its `const` definition at line 85).
    - `src/pages/MonitoringPage.jsx:191:9` & `192:9`: Unused variables `profile` and `thresholds`.
    - `src/pages/ComparePage.jsx:13:10`: Unused variable `comparing`.
    - `src/context/AuthContext.jsx:68:17`: `react(only-export-components)`: Fast refresh warning due to exporting `useAuth` hook from component file.
    - Cascading `react(set-state-in-effect)` and `react-hooks(exhaustive-deps)` across `AlertsPage.jsx`, `ShipmentsPage.jsx`, `ProductsPage.jsx`, `DashboardPage.jsx`, and `MonitoringPage.jsx`.

### 1.2 Routing & Component Hierarchy
- **Entry Point** (`frontend/src/main.jsx`): Wraps `<App />` in `<StrictMode>`.
- **Router Tree** (`frontend/src/App.jsx`):
  ```
  <AuthProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="shipments" element={<ShipmentsPage />} />
          <Route path="shipments/create" element={<CreateShipmentPage />} />
          <Route path="monitoring" element={<MonitoringPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="ml-analysis" element={<MLAnalysisPage />} />
          <Route path="what-if" element={<WhatIfPage />} />
          <Route path="compare" element={<ComparePage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </AuthProvider>
  ```
- **Layout Structure** (`frontend/src/components/Layout.jsx` & `Sidebar.jsx`):
  - Persistent sidebar for desktop (`--sidebar-width: 260px`).
  - Mobile slide-out drawer with backdrop blur (`.sidebar-backdrop`) triggered by top hamburger button.
  - Top header with dynamic page title and simulated status badge (`Simulated IoT Online`).
  - iOS-style fixed bottom tab bar for quick navigation on viewports `<= 900px` (`Overview`, `Shipments`, `Monitor`, `Alerts`, `ML Risk`, `What-If`).

### 1.3 Module 1: Auth & Executive Dashboard
- **Authentication** (`LoginPage.jsx`, `AuthContext.jsx`, `api.js`):
  - Supports Login and Registration with pre-populated demo login buttons (`Admin (Admin@1234)`, `Operator (Operator@1234)`).
  - Registration captures `username`, `password`, `email`, `full_name`, and `role` (`operator` vs `admin`).
  - `AuthContext.jsx:62`: Computes and provides `isAdmin: user?.role === 'admin'`.
  - **Direct Observation**: `grep -rn "isAdmin" src` confirms `isAdmin` is **never referenced or used** in any component anywhere in the frontend.
- **Executive Dashboard** (`DashboardPage.jsx`):
  - Summary KPI cards: Total Shipments, Active Journeys, Completed Journeys, High-Risk Shipments, Total Exposure Alerts, Average ML Risk Score.
  - Visual charts:
    - Doughnut chart: ML Quality Risk Distribution (`Low Risk`, `Medium Risk`, `High Risk`, `Unpredicted`).
    - Bar chart: Shipment Journey Status Overview (`Pending`, `In Transit`, `Paused`, `Stopped`, `Completed`).
  - Data tables: Recent Shipment Activity (6 items) and Recent Exposure Alerts (6 items).
  - **Direct Observation**: There are **no temperature or humidity monitoring cards** on `DashboardPage.jsx`, even though the Module 1 specification specifies "temperature & humidity monitoring" on the dashboard.
  - Backend `getDashboardStats()` (`backend/app/routes/dashboard_routes.py:63`) returns `transport_distribution`, but `DashboardPage.jsx` never renders it.

### 1.4 Module 2: Shipment Management
- **Listing & Filters** (`ShipmentsPage.jsx`):
  - Filters by Status (`Pending`, `In Transit`, `Paused`, `Stopped`, `Completed`) and Category (`fruits_vegetables`, `dairy`, `frozen`, `pharmaceutical`, `flowers`).
  - Table columns: Shipment ID (link), Product & Category, Origin & Destination, Transport Carrier, Status & Progress, Telemetry count & Alerts, ML Quality Risk badge/score, Actions.
- **Creation** (`CreateShipmentPage.jsx`):
  - Automatically loads product profiles (`/api/products`) and predefined locations (`/api/shipments/locations`).
  - Displays product profile safe bounds preview (min/max temp, min/max humidity, sensitivity).
  - Collects origin, destination, transport carrier, planned journey duration, and handling notes.
- **Defects & Spec Inconsistencies Observed**:
  - **No Shipment Edit UI**: While `api.updateShipment(id, data)` is defined in `api.js:103`, `updateShipment` is **never imported or called** anywhere in the frontend. There is no edit button in `ShipmentsPage.jsx`, no edit route, and no edit modal.
  - **Native `window.confirm` instead of Modal**: In `ShipmentsPage.jsx:31`:
    ```javascript
    if (!window.confirm(`Are you sure you want to delete shipment ${code}? ...`)) return;
    ```
    This uses the browser's native blocking popup instead of a styled confirmation modal.
  - **No Dedicated Details View**: Clicking shipment code navigates straight to `/monitoring?shipment=${s.id}`. There is no modal or view to inspect static shipment details (coordinates, timestamps, created by, notes) without viewing live simulation.

### 1.5 Module 3: IoT Sensor Simulator UI & Leaflet Map
- **Simulation Controls** (`MonitoringPage.jsx:300-388`):
  - Mode selector dropdown: `NORMAL`, `WARNING`, `CRITICAL`.
  - Tick rate selector: 1s, 2s, 5s.
  - Step jump: +5m, +15m, +30m.
  - Action buttons:
    - When Pending/Stopped/Completed: `🚀 Start Virtual Journey`.
    - When In Transit: `⏸ Pause Simulation`, `⏹ Stop Journey`, `✓ Mark Completed`.
    - When Paused: `▶ Resume Simulation`, `⏹ Stop`.
  - Manual trigger button: `⚡ Run ML Assessment Now` (`handlePredictNow()`).
- **Telemetry Visualizations**:
  - Top KPI cards: Current Temperature (with target threshold comparison), Current Humidity (with target bounds), Predicted Risk Class & Score, Active Exposure Alerts count.
  - Dual Chart.js Line charts: Temperature Telemetry History and Relative Humidity History with dashed threshold boundary lines.
  - Table of Harmful Exposure Incidents & Active Alerts.
- **Leaflet Map Defects Observed** (`MonitoringPage.jsx:86-147`):
  - **Duplicate Marker Stacking / Memory Leak**:
    Lines 105-120 execute `L.circleMarker(...).addTo(map)` on every effect run. Because `telemetry` updates every 2 seconds via `setInterval`, new origin and destination markers are continuously added on top of existing ones without cleanup.
  - **No Cleanup / StrictMode Crash Risk**:
    There is no `return () => map.remove()` cleanup in the Leaflet `useEffect`. Navigating back and forth can trigger `Error: Map container is already initialized`.
  - **No Map Re-centering**:
    When the user selects a different shipment from the dropdown, `leafletMapRef.current` is not reset or re-centered to the new coordinates; only the truck marker moves.

### 1.6 Module 7: What-If Journey Simulator UI
- **Workflow & Layout** (`WhatIfPage.jsx`):
  - Dropdown to select target shipment.
  - Sliders:
    - Average Temperature (`avgTemp`: -30°C to +40°C)
    - Peak Temperature (`maxTemp`: -25°C to +50°C)
    - Average Humidity (`avgHumidity`: 10% to 100% RH)
    - Temperature Exposure Duration (`tempExpHours`: 0h to `journeyDuration`h)
    - Journey Duration (`journeyDuration`: 2h to 120h)
    - Environmental Violations (`violationCount`: 0 to 30)
  - Action button: `Re-Run Model Simulation`.
  - Scenario saving: Input for scenario name + `Save` button calling `/simulator/what-if` and refreshing `/simulator/scenarios/${shipmentId}`.
  - Output displays:
    - Side-by-side cards: "Original Baseline" vs "Simulated Outcome".
    - Risk Shift Delta Banner (`result.score_difference`).
    - Comparison Bar Chart.
    - Modified Input Parameters shift factors table (`original_value`, `modified_value`, `delta`).
    - Saved Scenarios history table.
- **Defects Observed**:
  - **Missing Humidity Exposure Duration Slider**:
    In `WhatIfPage.jsx:19`, `const [humExpHours, setHumExpHours] = useState(0.0)` is defined, initialized from shipment stats (line 64), and sent in the simulation payload (line 93). However, **no range slider exists in the UI for `humExpHours`**! Users cannot adjust humidity exposure duration in What-If simulations.
  - **Initialization Order / TDZ Bug**:
    `runSimulation` is referenced on line 69 inside the `useEffect` before `const runSimulation = ...` is defined at line 85.

### 1.7 Module 8: Shipment Risk Comparison UI
- **Workflow & Layout** (`ComparePage.jsx`):
  - Checkbox selection grid for all available shipments (minimum 2).
  - Automatically runs comparison on initial mount if `>= 2` shipments exist.
  - Displays:
    - Cross-Category warning banner (`comparison.category_warning`) when comparing shipments from different product categories.
    - Safest Journey banner (`comparison.safest_shipment`) highlighting lowest risk score and reason.
    - Side-by-side comparison cards for each shipment showing: code, product, category, route, carrier, avg/peak temp, temp exposure hours, violations, alerts, risk badge, and score.
    - Bar chart comparing risk score vs temperature exposure duration across selected shipments.
- **Defects Observed**:
  - `comparing` state is set on lines 40 & 49 (`setComparing(true/false)`), but is **never used** to show a loading spinner or disable selection inputs during in-flight network requests.
  - If an unpredicted shipment is selected, risk score displays as 0 or "Awaiting Run", but there is no inline "Run Prediction" button on `ComparePage` to evaluate it without leaving the page.

### 1.8 Module 9: Report Download UI
- **Workflow & Layout** (`ReportsPage.jsx`):
  - Table of all consignments with status, readings count, alerts logged, predicted risk, and download button.
  - Report download link uses direct anchor: `<a href={api.getPdfReportUrl(s.id)} target="_blank">📄 Download PDF</a>`.
- **Defects Observed**:
  - **No Download Loading or Progress State**: Generating a multi-page ReportLab PDF on the fly takes time; an `<a>` tag gives zero visual feedback in the UI while the server generates the PDF.
  - **No Error Handling for Report Generation**: If the backend throws an error during PDF generation, the user is navigated to a browser page with raw JSON error text.
  - **Silent Failure on Shipments Fetch**: In `ReportsPage.jsx:13-17`, if `api.getShipments()` fails, the error is caught, `console.error` is called, and the page renders an empty table with no error banner.
  - **Decoupled Button on Shipments Table**: On `ShipmentsPage.jsx:186`, the "Report" button navigates to `/reports` rather than downloading the report for that specific shipment or pre-filtering the reports table.

### 1.9 Code Hygiene, Visual Styling & Dead Assets
- **`index.html` Title**: HTML document title is `<title>frontend</title>`, which is the default unconfigured Vite placeholder.
- **Dead Stylesheet**: `frontend/src/App.css` (184 lines) contains default Vite boilerplate (`.counter`, `.hero`, `#next-steps`, `.ticks`) and is never imported by `App.jsx` or any other file.

---

## 2. Logic Chain

1. **Premise 1 (Spec vs Code for Module 2)**:
   - The specification requires: "Create, edit, delete with confirmation modal, details view, start/stop virtual journeys, mark completed, unique IDs."
   - In `src/services/api.js:103`, `updateShipment` is implemented.
   - However, a codebase-wide grep for `updateShipment` yields only its declaration in `api.js`.
   - Inspection of `ShipmentsPage.jsx` shows action buttons strictly for "Monitor", "Report", and "✕" (Delete). No edit action exists.
   - Line 31 of `ShipmentsPage.jsx` uses `window.confirm()` rather than a React modal.
   - **Deduction**: Module 2 lacks shipment editing capabilities and compliant modal deletion.

2. **Premise 2 (Spec vs Code for Module 1 RBAC)**:
   - The specification requires admin and operator roles with role-based controls.
   - `AuthContext.jsx:62` provides `isAdmin: user?.role === 'admin'`.
   - Grep verification across all JSX files confirms `isAdmin` is not imported or consumed in any view.
   - `ProductsPage.jsx` allows any user to create and update product profiles without role gating.
   - **Deduction**: Role-based access control is currently only decorative (in the user profile badge) and is not enforced in the UI.

3. **Premise 3 (Dashboard Environmental Observability)**:
   - Module 1 requires "temperature & humidity monitoring" on the Dashboard.
   - Inspection of `DashboardPage.jsx` shows 6 summary cards for shipment totals, risk counts, alerts, and average risk score, plus status and risk charts.
   - Zero temperature or humidity metrics are rendered on `DashboardPage.jsx`.
   - **Deduction**: The dashboard satisfies high-level shipment KPIs but omits aggregated environmental compliance and condition metrics.

4. **Premise 4 (Leaflet Map Lifecycle in React 19)**:
   - In `MonitoringPage.jsx:86-147`, `useEffect` depends on `[currentShipment, telemetry]`.
   - `telemetry` is polled every 2000ms.
   - Inside the effect, `L.circleMarker(...).addTo(map)` is executed without removing previous circle markers.
   - `truckMarkerRef.current` and `routePolylineRef.current` update coordinates, but the map bounds never reset when switching shipments.
   - No teardown cleanup function is returned.
   - **Deduction**: A continuous memory leak occurs as markers accumulate every 2 seconds, and switching shipments leaves the map centered on the previous route.

5. **Premise 5 (Module 7 What-If Completeness)**:
   - The backend `/simulator/what-if` supports 6 numerical input dimensions including `humidity_exposure_hours`.
   - In `WhatIfPage.jsx`, state `humExpHours` is tracked and transmitted, but the JSX template only renders 5 sliders (avg temp, peak temp, avg humidity, temp exposure hours, journey duration, violation count).
   - **Deduction**: Users cannot simulate humidity exposure variations because the slider was omitted from the template.

---

## 3. Caveats

- **Backend Runtime Dependency**: This investigation surveyed the frontend React code and verified backend API contracts statically and through existing route implementations.
- **Serverless Constraints**: Vercel execution relies on `/tmp` for SQLite and disables threaded background simulation (`SIM_ENGINE_ENABLED = 0` in `api/index.py`). In serverless mode, simulated journeys advance via tick endpoints rather than background threads.
- **Scope Boundary**: This report focuses on frontend architecture and UI workflows. Backend ML model weights, scikit-learn pipeline details, and SQLite WAL settings are covered by the backend survey.

---

## 4. Conclusion

The frontend is a well-structured, modern React 19 single-page application built on Vite 8, featuring responsive styling inspired by Apple design guidelines (translucent navigation, fluid animations, touch-friendly hit areas, and mobile bottom tab bar). All primary views for the 9 modules are routed and functional.

However, the survey identified **10 critical deficiencies and specification gaps**:
1. **Missing Shipment Edit Feature**: `PUT /api/shipments/:id` exists in `api.js`, but no UI exists to edit shipments.
2. **Missing Delete Confirmation Modal**: Deletion uses native `window.confirm()` instead of a styled in-app modal.
3. **Missing Role-Based UI Gating**: `isAdmin` from `AuthContext` is unused; operators have identical UI access to admins.
4. **Missing Dashboard Environmental Monitoring**: Executive dashboard lacks aggregated temperature/humidity condition widgets.
5. **Leaflet Map Marker Leak & Bounds Bug**: Circular markers duplicate every 2 seconds during polling; map fails to re-center when changing shipments; missing cleanup on unmount.
6. **Missing What-If Humidity Slider**: `humExpHours` state exists but has no slider in `WhatIfPage.jsx`.
7. **What-If TDZ Variable Warning**: `runSimulation` accessed in `useEffect` prior to its definition.
8. **Unused UI States**: `comparing` in `ComparePage.jsx` and unused variables in `MonitoringPage.jsx` and `WhatIfPage.jsx`.
9. **Report Download Feedback & Error Gaps**: PDF download uses a plain anchor tag without loading state or error handling; `ReportsPage.jsx` fails silently if shipment loading fails.
10. **Cosmetic / Boilerplate Cleanliness**: `index.html` has placeholder title `<title>frontend</title>`, and `App.css` is dead boilerplate code.

---

## 5. Verification Method

To independently verify the observations and findings in this report:

1. **Verify Build and Linting**:
   ```bash
   cd /Users/porandlarajkumar/Documents/IOT/frontend
   npm run lint
   npm run build
   ```
   *Expected output*: `vite build` completes successfully; `oxlint` reports 20 warnings including `react(immutability)` in `WhatIfPage.jsx` and unused variables.

2. **Verify Missing Shipment Edit UI**:
   - Inspect `frontend/src/pages/ShipmentsPage.jsx` lines 181-201. Note there are only `Monitor`, `Report`, and `Delete` action buttons.
   - Grep for `updateShipment`:
     ```bash
     grep -rn "updateShipment" /Users/porandlarajkumar/Documents/IOT/frontend/src
     ```
     Confirms `updateShipment` is only present in `api.js:103` and never called.

3. **Verify Leaflet Marker Leak in MonitoringPage**:
   - Inspect `frontend/src/pages/MonitoringPage.jsx` lines 105-120. Notice `L.circleMarker(...).addTo(map)` is inside an effect that re-runs on every `telemetry` update with no marker clearing or layer group management.

4. **Verify Missing What-If Slider**:
   - Inspect `frontend/src/pages/WhatIfPage.jsx` lines 169-258. Verify that sliders exist for `avgTemp`, `maxTemp`, `avgHumidity`, `tempExpHours`, `journeyDuration`, and `violationCount`, but `humExpHours` is absent.

5. **Verify RBAC Absence**:
   - Grep for `isAdmin` across `frontend/src`:
     ```bash
     grep -rn "isAdmin" /Users/porandlarajkumar/Documents/IOT/frontend/src
     ```
     Confirms it only exists in `AuthContext.jsx:62`.
