"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "./Sidebar";
import { ChatHeader } from "./ChatHeader";
import { ChatView } from "../chat/ChatView";
import { AmbientBackground } from "../visual/AmbientBackground";
import { StudyToolsModal } from "../study/StudyToolsModal";
import { LibraryModal } from "../documents/LibraryModal";
import {
  dentalApi,
  ChatMessage,
  ConversationItem,
  DentalDocument,
} from "@/services/api";

export function AppShell() {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isStudyModalOpen, setIsStudyModalOpen] = useState(false);
  const [isLibraryModalOpen, setIsLibraryModalOpen] = useState(false);
  const [isBackendOnline, setIsBackendOnline] = useState(true);
  const [composerText, setComposerText] = useState("");

  // Initial load
  useEffect(() => {
    checkHealthAndInit();
  }, []);

  const checkHealthAndInit = async () => {
    const health = await dentalApi.checkHealth();
    setIsBackendOnline(health.status !== "offline");

    const convs = await dentalApi.getConversations();
    setConversations(convs);
    if (convs.length > 0) {
      // Auto-load most recent conversation
      selectConversation(convs[0].id);
    }
  };

  const selectConversation = async (id: string) => {
    setCurrentConversationId(id);
    const msgs = await dentalApi.getMessages(id);
    setMessages(msgs);
    setIsSidebarOpen(false);
  };

  const handleNewChat = () => {
    setCurrentConversationId(null);
    setMessages([]);
    setIsSidebarOpen(false);
  };

  const handleDeleteConversation = async (id: string) => {
    const success = await dentalApi.deleteConversation(id);
    if (success) {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentConversationId === id) {
        handleNewChat();
      }
    }
  };

  const handleSendMessage = async (text: string, documentId?: string, mode?: string) => {
    // 1. Optimistic user message
    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // 2. Call backend
      const res = await dentalApi.sendChat(
        text,
        currentConversationId || undefined,
        documentId
      );

      // 3. Update or set conversation ID
      if (!currentConversationId && res.conversation_id) {
        setCurrentConversationId(res.conversation_id);
        const updatedConvs = await dentalApi.getConversations();
        setConversations(updatedConvs);
      }

      // 4. Append assistant response
      const assistantMsg: ChatMessage = {
        id: `ast-${Date.now()}`,
        role: "assistant",
        content: res.message,
        provider: res.provider,
        model: res.model,
        latency_ms: res.latency_ms,
        citations: res.citations,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: unknown) {
      const fallbackMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: "I'm having a brief connection issue right now. Please try your question again in a moment.",
      };
      setMessages((prev) => [...prev, fallbackMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUploadDocument = async (file: File): Promise<DentalDocument> => {
    const doc = await dentalApi.uploadDocument(file);
    return doc;
  };

  const currentTitle =
    conversations.find((c) => c.id === currentConversationId)?.title ||
    (messages.length > 0 ? "Current Study Session" : "New Study Session");

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-[var(--bg-base)] text-[var(--text-primary)]">
      {/* Pearlescent Ambient Lighting */}
      <AmbientBackground />

      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={selectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        onOpenStudyTools={() => setIsStudyModalOpen(true)}
        onOpenLibrary={() => setIsLibraryModalOpen(true)}
        isOpen={isSidebarOpen}
        onToggleOpen={() => setIsSidebarOpen((prev) => !prev)}
      />

      {/* Main Workspace Column */}
      <div className="flex-1 flex flex-col h-full overflow-hidden lg:pl-[270px]">
        <ChatHeader
          title={currentTitle}
          onOpenSidebar={() => setIsSidebarOpen(true)}
          isBackendOnline={isBackendOnline}
        />

        <ChatView
          messages={messages}
          isLoading={isLoading}
          onSendMessage={handleSendMessage}
          onUploadDocument={handleUploadDocument}
          composerText={composerText}
          onComposerTextChange={setComposerText}
        />
      </div>

      {/* Modals */}
      <StudyToolsModal
        isOpen={isStudyModalOpen}
        onClose={() => setIsStudyModalOpen(false)}
      />

      <LibraryModal
        isOpen={isLibraryModalOpen}
        onClose={() => setIsLibraryModalOpen(false)}
        onSelectDocumentForChat={(doc) => {
          setComposerText(`What are the key concepts from ${doc.filename}?`);
        }}
      />
    </div>
  );
}
