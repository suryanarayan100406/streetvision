import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Map from './pages/Map';
import PotholeDetail from './pages/PotholeDetail';
import Kanban from './pages/Kanban';
import Leaderboard from './pages/Leaderboard';
import Analytics from './pages/Analytics';

export default function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Map />} />
          <Route path="/pothole/:id" element={<PotholeDetail />} />
          <Route path="/kanban" element={<Kanban />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </Layout>
    </Router>
  );
}
