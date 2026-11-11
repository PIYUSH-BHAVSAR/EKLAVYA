import { Routes, Route, Navigate } from "react-router-dom";
import { useState, useCallback } from "react";
import CitizenSidebar from "./CitizenSidebar";
import ChatPage from "./ChatPage";
import { SourceDrawer } from "./SourceDrawer";
import { Citation } from "../../api";
import LlmStatusChip from "../../components/LlmStatusChip";

export interface DrawerState {
  open: boolean;
  docId: number;
  pageNo: number;
  quote: string;
  grNumber: string;
  grDate: string;
}

const DRAWER_CLOSED: DrawerState = {
  open: false, docId: 0, pageNo: 1, quote: "", grNumber: "", grDate: "",
};

export default function CitizenLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [drawer, setDrawer] = useState<DrawerState>(DRAWER_CLOSED);
  const [prefill, setPrefill] = useState<string>("");

  const openDrawer = useCallback((c: Citation) => {
    setDrawer({
      open: true,
      docId: c.doc_id,
      pageNo: c.page,
      quote: c.quote,
      grNumber: c.gr_number,
      grDate: c.gr_date,
    });
  }, []);

  const handleStarterClick = useCallback((q: string) => {
    setPrefill(q);
    // Reset after a tick so ChatPage picks up the new value
    setTimeout(() => setPrefill(""), 100);
  }, []);

  return (
    <div className="flex h-screen bg-light overflow-hidden">
      {/* Sidebar */}
      <CitizenSidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(o => !o)}
        onStarterClick={handleStarterClick}
      />

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <Routes>
          <Route path="chat" element={<ChatPage openDrawer={openDrawer} prefillQuestion={prefill} />} />
          <Route path="*" element={<Navigate to="chat" replace />} />
        </Routes>
        {/* Offline AI status footer */}
        <div className="shrink-0 px-4 py-2 border-t border-gray-100 bg-white flex justify-center">
          <LlmStatusChip variant="footer" />
        </div>
      </div>

      {/* Source drawer */}
      {drawer.open && (
        <SourceDrawer
          docId={drawer.docId}
          pageNo={drawer.pageNo}
          quote={drawer.quote}
          grNumber={drawer.grNumber}
          grDate={drawer.grDate}
          onClose={() => setDrawer(DRAWER_CLOSED)}
        />
      )}
    </div>
  );
}
