"use client";

import React, { useState } from "react";
import {
  Plus,
  Search,
  MessageSquare,
  BookOpen,
  History,
  GraduationCap,
  Trash2,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  User,
} from "lucide-react";
import { ConversationItem } from "@/services/api";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

interface SidebarProps {
  conversations: ConversationItem[];
  currentConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onDeleteConversation: (id: string) => void;
  onOpenStudyTools?: () => void;
  onOpenLibrary?: () => void;
  isOpen: boolean;
  onToggleOpen: () => void;
}

export function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  onOpenStudyTools,
  onOpenLibrary,
  isOpen,
  onToggleOpen,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onToggleOpen}
          className="fixed inset-0 bg-black/30 backdrop-blur-xs z-30 lg:hidden"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 flex flex-col w-[270px] glass-panel border-r border-[var(--border-light)] transition-all duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0 lg:w-[270px]"
        }`}
      >
        {/* Top Header: Brand & New Chat */}
        <div className="p-4 border-b border-[var(--border-light)]">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              {/* Pearl Glyph */}
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-violet-300 via-white to-purple-200 border border-violet-300/40 pearl-glow flex items-center justify-center">
                <Sparkles className="w-3.5 h-3.5 text-violet-600" />
              </div>
              <div>
                <h1 className="font-semibold text-sm tracking-tight text-[var(--text-primary)]">
                  Sristi AI
                </h1>
                <p className="text-[10px] text-[var(--text-muted)]">Dental Study Companion</p>
              </div>
            </div>

            <ThemeToggle />
          </div>

          {/* New Chat Button */}
          <button
            onClick={onNewChat}
            className="w-full flex items-center justify-center gap-2 py-2 px-3.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-medium shadow-sm transition-all duration-200 hover:shadow-md cursor-pointer active:scale-98"
          >
            <Plus className="w-4 h-4" />
            <span>New Study Session</span>
          </button>
        </div>

        {/* Quick Nav Library Links */}
        <div className="px-3 pt-3 pb-2 space-y-1 text-xs text-[var(--text-secondary)] border-b border-[var(--border-light)]">
          <button
            onClick={onOpenLibrary}
            className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left cursor-pointer"
          >
            <BookOpen className="w-3.5 h-3.5 text-violet-500" />
            <span>Textbook Library</span>
          </button>

          <button
            onClick={onOpenStudyTools}
            className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left cursor-pointer"
          >
            <GraduationCap className="w-3.5 h-3.5 text-rose-500" />
            <span>Flashcards & Quizzes</span>
          </button>
        </div>

        {/* Search Input */}
        <div className="p-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search conversations..."
              className="w-full pl-8 pr-2.5 py-1.5 rounded-lg bg-black/5 dark:bg-white/5 border border-transparent focus:border-[var(--border-light)] outline-none text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)]"
            />
          </div>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
          <div className="px-2 py-1 text-[11px] font-semibold tracking-wider uppercase text-[var(--text-muted)]">
            Recent Sessions
          </div>

          {filteredConversations.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-[var(--text-muted)]">
              No previous study sessions yet.
            </div>
          ) : (
            filteredConversations.map((conv) => {
              const isActive = conv.id === currentConversationId;
              return (
                <div
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  className={`group relative flex items-center justify-between px-2.5 py-2 rounded-xl text-xs transition-all cursor-pointer ${
                    isActive
                      ? "bg-violet-100/80 dark:bg-violet-950/60 text-violet-900 dark:text-violet-200 font-medium border border-violet-200 dark:border-violet-800"
                      : "text-[var(--text-secondary)] hover:bg-black/5 dark:hover:bg-white/5 hover:text-[var(--text-primary)]"
                  }`}
                >
                  <div className="flex items-center gap-2 truncate mr-2">
                    <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-violet-400" />
                    <span className="truncate">{conv.title}</span>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(conv.id);
                    }}
                    title="Delete session"
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:text-red-500 transition-opacity"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Bottom Profile Badge: Sristi Biswal */}
        <div className="p-3 border-t border-[var(--border-light)] bg-black/2 dark:bg-white/2">
          <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-xl">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-violet-500 to-indigo-400 text-white flex items-center justify-center font-semibold text-xs shadow-sm">
              SB
            </div>
            <div className="truncate">
              <div className="text-xs font-semibold text-[var(--text-primary)] truncate">
                Sristi Biswal
              </div>
              <div className="text-[10px] text-[var(--text-muted)] truncate">
                BDS Dental Scholar
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
