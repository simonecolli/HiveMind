import { BrowserRouter, Navigate, Route, Routes } from 'react-router';

import { ChatPage } from './features/chat/ChatPage';
import { SessionPage } from './features/chat/SessionPage';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { HistoryPage } from './features/history/HistoryPage';
import { Layout } from './features/shared/components/Layout';
import { AgentEditorPage } from './features/teams/AgentEditorPage';
import { TeamCreatePage } from './features/teams/TeamCreatePage';
import { TeamPage } from './features/teams/TeamPage';
import { TeamsListPage } from './features/teams/TeamsListPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />

          <Route path="chat" element={<ChatPage />} />
          <Route path="chat/:sessionId" element={<SessionPage />} />

          <Route path="teams" element={<TeamsListPage />} />
          <Route path="teams/new" element={<TeamCreatePage />} />
          <Route path="teams/:teamId" element={<TeamPage />} />
          {/* One page for both creating and editing an agent. */}
          <Route path="teams/:teamId/agents/new" element={<AgentEditorPage />} />
          <Route path="teams/:teamId/agents/:agentId" element={<AgentEditorPage />} />

          <Route path="history" element={<HistoryPage />} />

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
