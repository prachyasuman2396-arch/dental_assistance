"use client";

import React, { useRef, useState, useEffect } from "react";
import { ArrowUp, Paperclip, X, Sparkles, BookOpen, Search, GraduationCap } from "lucide-react";

interface ChatComposerProps {
  onSendMessage: (text: string, documentId?: string, mode?: string) => void;
  isLoading: boolean;
  onUploadDocument?: (file: File) => Promise<{ id: string; filename: string }>;
  initialText?: string;
  onTextChange?: (text: string) => void;
}

export function ChatComposer({
  onSendMessage,
  isLoading,
  onUploadDocument,
  initialText = "",
  onTextChange,
}: ChatComposerProps) {
  const [input, setInput] = useState(initialText);
  const [selectedMode, setSelectedMode] = useState<"tutor" | "research" | "study">("tutor");
  const [attachedDoc, setAttachedDoc] = useState<{ id: string; filename: string } | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialText !== undefined) {
      setInput(initialText);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
      }
    }
  }, [initialText]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);
    if (onTextChange) onTextChange(val);

    // Auto-grow
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    onSendMessage(trimmed, attachedDoc?.id, selectedMode);
    setInput("");
    if (onTextChange) onTextChange("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onUploadDocument) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please upload a PDF dental textbook or notes file.");
      return;
    }

    try {
      setIsUploading(true);
      const uploaded = await onUploadDocument(file);
      setAttachedDoc(uploaded);
    } catch (err) {
      alert("Failed to upload document. Please try again.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
      {/* Attached file chip */}
      {attachedDoc && (
        <div className="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-lg bg-violet-100/70 dark:bg-violet-950/50 border border-violet-200 dark:border-violet-800 text-xs text-violet-800 dark:text-violet-200 w-fit">
          <Paperclip className="w-3.5 h-3.5 text-violet-600 dark:text-violet-400" />
          <span className="font-medium truncate max-w-[220px]">{attachedDoc.filename}</span>
          <button
            onClick={() => setAttachedDoc(null)}
            className="p-0.5 rounded hover:bg-violet-200/50 dark:hover:bg-violet-900/50 cursor-pointer ml-1"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Floating Glass Capsule Composer */}
      <div className="relative rounded-2xl glass-elevated p-2 transition-all duration-300 border border-violet-300/30 dark:border-violet-500/20 shadow-xl focus-within:border-violet-500/40 focus-within:shadow-[0_0_25px_rgba(141,121,214,0.2)]">
        {/* Hidden file input */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".pdf"
          className="hidden"
        />

        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about dentistry, Sristi..."
          rows={1}
          className="w-full bg-transparent resize-none outline-none px-3 pt-2 pb-1 text-sm md:text-[15px] placeholder-[var(--text-muted)] text-[var(--text-primary)] max-h-[180px] leading-relaxed"
        />

        {/* Bottom controls row */}
        <div className="flex items-center justify-between pt-2 px-1 border-t border-[var(--border-light)] mt-1">
          {/* Mode Selector pills */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setSelectedMode("tutor")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                selectedMode === "tutor"
                  ? "bg-violet-100 dark:bg-violet-900/60 text-violet-700 dark:text-violet-300 border border-violet-300/40"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-black/5 dark:hover:bg-white/5"
              }`}
            >
              <Sparkles className="w-3 h-3" />
              Tutor
            </button>

            <button
              type="button"
              onClick={() => setSelectedMode("research")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                selectedMode === "research"
                  ? "bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 border border-blue-300/40"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-black/5 dark:hover:bg-white/5"
              }`}
            >
              <Search className="w-3 h-3" />
              Research
            </button>

            <button
              type="button"
              onClick={() => setSelectedMode("study")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                selectedMode === "study"
                  ? "bg-rose-100 dark:bg-rose-900/60 text-rose-700 dark:text-rose-300 border border-rose-300/40"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-black/5 dark:hover:bg-white/5"
              }`}
            >
              <GraduationCap className="w-3 h-3" />
              Quiz/MCQ
            </button>

            {/* Attachment Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              title="Upload Dental Textbook or Lecture Notes (PDF)"
              className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-950/50 transition-colors ml-1 cursor-pointer disabled:opacity-50"
            >
              <Paperclip className="w-4 h-4" />
            </button>
          </div>

          {/* Send Button */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!input.trim() || isLoading}
            aria-label="Send query"
            className={`p-2 rounded-xl transition-all duration-200 flex items-center justify-center cursor-pointer ${
              input.trim() && !isLoading
                ? "bg-gradient-to-tr from-violet-600 to-indigo-500 text-white shadow-md hover:scale-105 active:scale-95"
                : "bg-black/5 dark:bg-white/10 text-[var(--text-muted)] opacity-50 cursor-not-allowed"
            }`}
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
