"use client";

import React, { useRef, useEffect } from "react";
import { Sparkles } from "lucide-react";
import { ChatMessage, DentalDocument } from "@/services/api";
import { LuminousPearl } from "@/components/visual/LuminousPearl";
import { SuggestedPrompts } from "@/components/chat/SuggestedPrompts";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { UserMessage } from "@/components/chat/UserMessage";
import { AssistantMessage } from "@/components/chat/AssistantMessage";

interface ChatViewProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSendMessage: (text: string, documentId?: string, mode?: string) => void;
  onUploadDocument: (file: File) => Promise<DentalDocument>;
  composerText: string;
  onComposerTextChange: (text: string) => void;
}

export function ChatView({
  messages,
  isLoading,
  onSendMessage,
  onUploadDocument,
  composerText,
  onComposerTextChange,
}: ChatViewProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const isConversationEmpty = messages.length === 0;

  return (
    <div className="relative flex-1 flex flex-col h-full overflow-hidden">
      {/* Scrollable Conversation / Welcome Area */}
      <div className="flex-1 overflow-y-auto px-4 md:px-6 py-6 flex flex-col items-center">
        {isConversationEmpty ? (
          /* Welcome Screen Composition */
          <div className="w-full max-w-2xl flex flex-col items-center text-center my-auto py-8 animate-fade-in">
            {/* Luminous 3D Pearl Visual */}
            <div className="mb-4">
              <LuminousPearl size={220} />
            </div>

            {/* Personalized Welcome Header */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-100/60 dark:bg-violet-950/40 border border-violet-200/50 dark:border-violet-800/40 text-violet-700 dark:text-violet-300 text-xs font-semibold mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Hey Sristi ✨</span>
            </div>

            <h1 className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-[var(--text-primary)] mb-2">
              What shall we discover today?
            </h1>

            <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-lg mb-4 leading-relaxed">
              Your space to explore dentistry, understand the complex, and discover something new.
            </p>

            {/* 4 Suggested Action Cards */}
            <SuggestedPrompts
              onSelectPrompt={(promptText) => onComposerTextChange(promptText)}
            />
          </div>
        ) : (
          /* Active Chat Stream */
          <div className="w-full max-w-3xl flex flex-col pt-2 pb-6">
            {messages.map((m) => (
              <React.Fragment key={m.id}>
                {m.role === "user" ? (
                  <UserMessage content={m.content} />
                ) : (
                  <AssistantMessage
                    content={m.content}
                    provider={m.provider}
                    model={m.model}
                    latencyMs={m.latency_ms}
                    citations={m.citations}
                  />
                )}
              </React.Fragment>
            ))}

            {/* Thinking / Streaming Indicator */}
            {isLoading && (
              <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-2xl bg-black/3 dark:bg-white/5 border border-[var(--border-light)] w-fit mb-6 text-xs text-[var(--text-muted)] animate-pulse">
                <div className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                <span>Sristi AI is preparing your explanation...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Floating Composer */}
      <div className="w-full z-10">
        <ChatComposer
          onSendMessage={onSendMessage}
          isLoading={isLoading}
          onUploadDocument={onUploadDocument}
          initialText={composerText}
          onTextChange={onComposerTextChange}
        />
      </div>
    </div>
  );
}
