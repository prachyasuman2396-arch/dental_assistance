"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "./Sidebar";
import { ChatHeader } from "./ChatHeader";
import { ChatView } from "../chat/ChatView";
import { AmbientBackground } from "../visual/AmbientBackground";
import { StudyToolsModal } from "../study/StudyToolsModal";
import { LibraryModal } from "../documents/LibraryModal";
import {
  studyApi,
  ChatMessage,
  ConversationItem,
  StudyDocument,
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
    const health = await studyApi.checkHealth();
    setIsBackendOnline(health.status !== "offline");

    const convs = await studyApi.getConversations();
    setConversations(convs);
    if (convs.length > 0) {
      // Auto-load most recent conversation
      selectConversation(convs[0].id);
    }
  };

  const selectConversation = async (id: string) => {
    setCurrentConversationId(id);
    const msgs = await studyApi.getMessages(id);
    setMessages(msgs);
    setIsSidebarOpen(false);
  };

  const handleNewChat = () => {
    setCurrentConversationId(null);
    setMessages([]);
    setIsSidebarOpen(false);
  };

  const handleDeleteConversation = async (id: string) => {
    const success = await studyApi.deleteConversation(id);
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
    
    // Assistant streaming message placeholder
    const assistantMsgId = `ast-${Date.now()}`;
    const assistantPlaceholder: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);
    setIsLoading(true);

    let hasReceivedToken = false;

    try {
      await studyApi.streamChat(
        text,
        currentConversationId || undefined,
        documentId,
        {
          onStart: async (data) => {
            if (!currentConversationId && data.conversation_id) {
              setCurrentConversationId(data.conversation_id);
              const updatedConvs = await studyApi.getConversations();
              setConversations(updatedConvs);
            }
          },
          onToken: (data) => {
            hasReceivedToken = true;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      content: msg.content + data.token,
                      provider: data.provider || msg.provider,
                      model: data.model || msg.model,
                    }
                  : msg
              )
            );
          },
          onCitation: (data) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? { ...msg, citations: data.citations }
                  : msg
              )
            );
          },
          onEnd: (data) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      content: data.answer || msg.content,
                      provider: data.provider || msg.provider,
                      model: data.model || msg.model,
                      latency_ms: data.latency_ms,
                      citations: data.citations || msg.citations,
                    }
                  : msg
              )
            );
          },
          onError: (err) => {
            if (!hasReceivedToken) {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMsgId
                    ? {
                        ...msg,
                        content:
                          "I encountered a momentary issue processing that request. Please try again or rephrase your question.",
                      }
                    : msg
                )
              );
            }
          },
        }
      );
    } catch (e: unknown) {
      if (!hasReceivedToken) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content:
                    "I'm having a brief connection issue right now. Please try your question again in a moment.",
                }
              : msg
          )
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleUploadDocument = async (file: File): Promise<StudyDocument> => {
    const doc = await studyApi.uploadDocument(file);
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
