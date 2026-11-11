import { Routes, Route, Navigate } from "react-router-dom";
import AdminSidebar from "./AdminSidebar";
import OverviewPage from "./OverviewPage";
import PipelinePage from "./PipelinePage";
import DocumentsPage from "./DocumentsPage";
import RulesPage from "./RulesPage";
import ReviewPage from "./ReviewPage";
import SourcesPage from "./SourcesPage";
import QuestionsPage from "./QuestionsPage";
import EvaluationPage from "./EvaluationPage";
import GuardrailsPage from "./GuardrailsPage";
import AuditPage from "./AuditPage";
import SettingsPage from "./SettingsPage";

export default function AdminLayout() {
  return (
    <div className="flex h-screen bg-light overflow-hidden">
      <AdminSidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Saffron strip */}
        <div className="h-1 bg-saffron shrink-0" />
        <div className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="overview"    element={<OverviewPage />} />
            <Route path="pipeline"    element={<PipelinePage />} />
            <Route path="documents"   element={<DocumentsPage />} />
            <Route path="rules"       element={<RulesPage />} />
            <Route path="review"      element={<ReviewPage />} />
            <Route path="sources"     element={<SourcesPage />} />
            <Route path="questions"   element={<QuestionsPage />} />
            <Route path="evaluation"  element={<EvaluationPage />} />
            <Route path="guardrails"  element={<GuardrailsPage />} />
            <Route path="audit"       element={<AuditPage />} />
            <Route path="settings"    element={<SettingsPage />} />
            <Route path="*"           element={<Navigate to="overview" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
