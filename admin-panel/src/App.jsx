import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout';
import Login from './pages/Login';
import Overview from './pages/Overview';
import Satellites from './pages/Satellites';
import Drones from './pages/Drones';
import CCTV from './pages/CCTV';
import Pipeline from './pages/Pipeline';
import PipelineTest from './pages/PipelineTest';
import Detections from './pages/Detections';
import Models from './pages/Models';
import Scheduler from './pages/Scheduler';
import Settings from './pages/Settings';
import Logs from './pages/Logs';
import ModuleDetectionOutput from './pages/ModuleDetectionOutput';
import ModuleModelPredictions from './pages/ModuleModelPredictions';
import ModuleEscalationLogic from './pages/ModuleEscalationLogic';
import ModuleCompiledPipeline from './pages/ModuleCompiledPipeline';
import ModuleVerificationRecheck from './pages/ModuleVerificationRecheck';
import ModuleInferenceDecision from './pages/ModuleInferenceDecision';

function PrivateRoute({ children }) {
  const token = localStorage.getItem('access_token');
  return token ? children : <Navigate to="/login" />;
}

export default function App() {
  return (
    <>
      <Toaster position="top-right" />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Overview />} />
          <Route path="satellites" element={<Satellites />} />
          <Route path="drones" element={<Drones />} />
          <Route path="cctv" element={<CCTV />} />
          <Route path="pipeline" element={<Pipeline />} />
          <Route path="pipeline-test" element={<PipelineTest />} />
          <Route path="detections" element={<Detections />} />
          <Route path="models" element={<Models />} />
          <Route path="scheduler" element={<Scheduler />} />
          <Route path="settings" element={<Settings />} />
          <Route path="logs" element={<Logs />} />
          <Route path="module-detection-output" element={<ModuleDetectionOutput />} />
          <Route path="module-model-predictions" element={<ModuleModelPredictions />} />
          <Route path="module-escalation-logic" element={<ModuleEscalationLogic />} />
          <Route path="module-verification-recheck" element={<ModuleVerificationRecheck />} />
          <Route path="module-inference-decision" element={<ModuleInferenceDecision />} />
          <Route path="module-compiled-pipeline" element={<ModuleCompiledPipeline />} />
        </Route>
      </Routes>
    </>
  );
}
