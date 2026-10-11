"use client";

import React, { useState, useEffect } from "react";
import { X, BookOpen, Upload, FileText, CheckCircle2, Clock, AlertCircle } from "lucide-react";
import { dentalApi, DentalDocument } from "@/services/api";

interface LibraryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectDocumentForChat?: (doc: DentalDocument) => void;
}

export function LibraryModal({ isOpen, onClose, onSelectDocumentForChat }: LibraryModalProps) {
  const [documents, setDocuments] = useState<DentalDocument[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadDocs();
    }
  }, [isOpen]);

  const loadDocs = async () => {
    const docs = await dentalApi.getDocuments();
    setDocuments(docs);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsUploading(true);
      await dentalApi.uploadDocument(file);
      await loadDocs();
    } catch {
      alert("Failed to upload PDF. Please verify size (max 25MB).");
    } finally {
      setIsUploading(false);
      e.target.value = "";
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
      <div className="relative w-full max-w-xl max-h-[80vh] rounded-3xl glass-elevated border border-[var(--border-luminous)] shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-light)]">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-violet-100 dark:bg-violet-950/60 text-violet-600 dark:text-violet-400">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-semibold text-base text-[var(--text-primary)]">
                Textbook & Lecture Notes Library
              </h2>
              <p className="text-xs text-[var(--text-muted)]">
                Your personal study materials and referenced textbooks
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Upload Trigger */}
        <div className="p-4 border-b border-[var(--border-light)] bg-black/2 dark:bg-white/2">
          <label className="flex items-center justify-center gap-2 w-full py-3 px-4 rounded-2xl border-2 border-dashed border-violet-300 dark:border-violet-700 hover:border-violet-500 cursor-pointer transition-colors text-xs font-medium text-violet-700 dark:text-violet-300">
            <Upload className="w-4 h-4" />
            <span>{isUploading ? "Adding to your study library..." : "Upload Dental Textbook or Notes (PDF)"}</span>
            <input
              type="file"
              accept=".pdf"
              onChange={handleUpload}
              disabled={isUploading}
              className="hidden"
            />
          </label>
        </div>

        {/* Documents List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {documents.length === 0 ? (
            <div className="text-center py-10 text-xs text-[var(--text-muted)]">
              No dental documents uploaded yet. Upload lecture notes or textbooks above.
            </div>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between p-3.5 rounded-2xl glass-panel border border-[var(--border-light)] text-xs transition-all hover:border-violet-300/40"
              >
                <div className="flex items-center gap-3 truncate mr-2">
                  <div className="p-2 rounded-xl bg-violet-50 dark:bg-violet-950/50 text-violet-600">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div className="truncate">
                    <div className="font-semibold text-[var(--text-primary)] truncate">
                      {doc.filename}
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)] flex items-center gap-2">
                      <span>{doc.page_count} pages</span>
                      <span>•</span>
                      <span>{(doc.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  {doc.status === "completed" ? (
                    <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                      <CheckCircle2 className="w-3 h-3" /> Ready
                    </span>
                  ) : doc.status === "processing" ? (
                    <span className="flex items-center gap-1 text-[10px] font-medium text-amber-600 bg-amber-500/10 px-2 py-0.5 rounded-full">
                      <Clock className="w-3 h-3" /> Processing
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] font-medium text-rose-600 bg-rose-500/10 px-2 py-0.5 rounded-full">
                      <AlertCircle className="w-3 h-3" /> Error
                    </span>
                  )}

                  {onSelectDocumentForChat && doc.status === "completed" && (
                    <button
                      onClick={() => {
                        onSelectDocumentForChat(doc);
                        onClose();
                      }}
                      className="px-2.5 py-1 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-[11px] font-medium transition-colors cursor-pointer"
                    >
                      Study This
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
