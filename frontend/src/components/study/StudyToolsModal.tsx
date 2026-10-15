"use client";

import React, { useState } from "react";
import { X, GraduationCap, Sparkles, CheckCircle2, HelpCircle, Calendar, MessageSquare } from "lucide-react";
import { studyApi, QuizQuestion, Flashcard } from "@/services/api";

interface StudyToolsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function StudyToolsModal({ isOpen, onClose }: StudyToolsModalProps) {
  const [activeTab, setActiveTab] = useState<"quiz" | "flashcards" | "viva" | "plan">("quiz");
  const [topic, setTopic] = useState("Cellular Respiration & Metabolism");
  const [isLoading, setIsLoading] = useState(false);
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([]);
  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [vivaItems, setVivaItems] = useState<any[]>([]);
  const [studyPlan, setStudyPlan] = useState<any | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
  const [revealedFlashcards, setRevealedFlashcards] = useState<Record<number, boolean>>({});

  if (!isOpen) return null;

  const handleGenerate = async () => {
    if (!topic.trim()) return;
    try {
      setIsLoading(true);
      if (activeTab === "quiz") {
        const res = await studyApi.generateQuiz(topic, 3);
        setQuizQuestions(res);
        setSelectedAnswers({});
      } else if (activeTab === "flashcards") {
        const res = await studyApi.generateFlashcards(topic, 4);
        setFlashcards(res);
        setRevealedFlashcards({});
      } else if (activeTab === "viva") {
        const res = await studyApi.generateViva(topic, 3);
        setVivaItems(res);
      } else if (activeTab === "plan") {
        const res = await studyApi.generateStudyPlan(topic, 4, 12);
        setStudyPlan(res);
      }
    } catch (e) {
      console.error(e);
      alert("Failed to generate study materials. Please check your backend connection.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
      <div className="relative w-full max-w-2xl max-h-[85vh] rounded-3xl glass-elevated border border-[var(--border-luminous)] shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-light)]">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-violet-100 dark:bg-violet-950/60 text-violet-600 dark:text-violet-400">
              <GraduationCap className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-semibold text-base text-[var(--text-primary)]">
                Exam Preparation & Study Workflows
              </h2>
              <p className="text-xs text-[var(--text-muted)]">
                Practice high-yield MCQs, active-recall flashcards, viva voce, and study schedules
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

        {/* Tab & Generator Controls */}
        <div className="p-5 border-b border-[var(--border-light)] space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
            <button
              onClick={() => setActiveTab("quiz")}
              className={`py-2 text-xs font-semibold rounded-xl transition-all cursor-pointer ${
                activeTab === "quiz"
                  ? "bg-violet-600 text-white shadow-sm"
                  : "bg-black/5 dark:bg-white/5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Exam MCQs
            </button>
            <button
              onClick={() => setActiveTab("flashcards")}
              className={`py-2 text-xs font-semibold rounded-xl transition-all cursor-pointer ${
                activeTab === "flashcards"
                  ? "bg-violet-600 text-white shadow-sm"
                  : "bg-black/5 dark:bg-white/5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Flashcards
            </button>
            <button
              onClick={() => setActiveTab("viva")}
              className={`py-2 text-xs font-semibold rounded-xl transition-all cursor-pointer ${
                activeTab === "viva"
                  ? "bg-violet-600 text-white shadow-sm"
                  : "bg-black/5 dark:bg-white/5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Oral Viva
            </button>
            <button
              onClick={() => setActiveTab("plan")}
              className={`py-2 text-xs font-semibold rounded-xl transition-all cursor-pointer ${
                activeTab === "plan"
                  ? "bg-violet-600 text-white shadow-sm"
                  : "bg-black/5 dark:bg-white/5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Study Plan
            </button>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Enter subject or study topic..."
              className="flex-1 px-3.5 py-2 rounded-xl bg-black/5 dark:bg-white/5 border border-[var(--border-light)] text-xs text-[var(--text-primary)] outline-none focus:border-violet-400"
            />
            <button
              onClick={handleGenerate}
              disabled={isLoading || !topic.trim()}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-xs font-medium shadow-sm hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Generate</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {activeTab === "quiz" && (
            <>
              {quizQuestions.length === 0 ? (
                <div className="text-center py-12 text-xs text-[var(--text-muted)]">
                  Enter a study topic and click Generate to practice high-yield MCQs.
                </div>
              ) : (
                quizQuestions.map((q, idx) => {
                  const userAns = selectedAnswers[idx];
                  return (
                    <div
                      key={idx}
                      className="p-4 rounded-2xl glass-panel space-y-3 text-xs border border-[var(--border-light)]"
                    >
                      <div className="font-semibold text-sm text-[var(--text-primary)]">
                        {idx + 1}. {q.question}
                      </div>

                      <div className="space-y-1.5">
                        {q.options.map((opt, optIdx) => {
                          const isSelected = userAns === opt;
                          const isCorrect = opt === q.correct_answer;
                          let btnStyle = "bg-black/5 dark:bg-white/5 hover:bg-violet-50 dark:hover:bg-violet-950/40";
                          if (userAns) {
                            if (isCorrect) btnStyle = "bg-emerald-500/15 border-emerald-500 text-emerald-800 dark:text-emerald-200";
                            else if (isSelected) btnStyle = "bg-rose-500/15 border-rose-500 text-rose-800 dark:text-rose-200";
                          }

                          return (
                            <button
                              key={optIdx}
                              onClick={() => setSelectedAnswers((prev) => ({ ...prev, [idx]: opt }))}
                              className={`w-full text-left px-3.5 py-2 rounded-xl border border-transparent transition-all cursor-pointer text-xs ${btnStyle}`}
                            >
                              {opt}
                            </button>
                          );
                        })}
                      </div>

                      {userAns && (
                        <div className="p-3 rounded-xl bg-violet-50/70 dark:bg-violet-950/40 border border-violet-200 dark:border-violet-800 text-[11px] leading-relaxed text-[var(--text-secondary)]">
                          <strong className="text-violet-700 dark:text-violet-300">Explanation: </strong>
                          {q.explanation}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </>
          )}

          {activeTab === "flashcards" && (
            <>
              {flashcards.length === 0 ? (
                <div className="text-center py-12 text-xs text-[var(--text-muted)]">
                  Enter a topic and click Generate to create active-recall revision flashcards.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {flashcards.map((fc, idx) => {
                    const isFlipped = revealedFlashcards[idx];
                    return (
                      <div
                        key={idx}
                        onClick={() =>
                          setRevealedFlashcards((prev) => ({ ...prev, [idx]: !prev[idx] }))
                        }
                        className="p-4 rounded-2xl glass-panel min-h-[140px] flex flex-col justify-between cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-md border border-[var(--border-light)]"
                      >
                        <div className="text-xs font-semibold text-[var(--text-primary)] leading-relaxed">
                          {isFlipped ? (
                            <span className="text-violet-600 dark:text-violet-300">{fc.answer}</span>
                          ) : (
                            fc.question
                          )}
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)] pt-2 border-t border-[var(--border-light)] flex justify-between items-center">
                          <span>{isFlipped ? "Answer" : "Question"}</span>
                          <span className="text-violet-500">Click to flip</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}

          {activeTab === "viva" && (
            <>
              {vivaItems.length === 0 ? (
                <div className="text-center py-12 text-xs text-[var(--text-muted)]">
                  Enter a topic and click Generate to practice oral examination viva questions.
                </div>
              ) : (
                <div className="space-y-3">
                  {vivaItems.map((v, idx) => (
                    <div key={idx} className="p-4 rounded-2xl glass-panel space-y-2.5 text-xs border border-[var(--border-light)]">
                      <div className="font-semibold text-sm text-[var(--text-primary)] flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-violet-500" />
                        <span>Viva Question {idx + 1}: {v.viva_question}</span>
                      </div>
                      <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 text-[var(--text-secondary)] leading-relaxed">
                        <strong className="text-[var(--text-primary)]">Model Answer: </strong>
                        {v.model_answer}
                      </div>
                      {v.key_examiner_points && v.key_examiner_points.length > 0 && (
                        <div className="text-[11px] text-violet-600 dark:text-violet-300">
                          <strong>Must-Know Points: </strong>
                          {v.key_examiner_points.join(" • ")}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {activeTab === "plan" && (
            <>
              {!studyPlan ? (
                <div className="text-center py-12 text-xs text-[var(--text-muted)]">
                  Enter your target subject or examination and click Generate to build a multi-week study schedule.
                </div>
              ) : (
                <div className="space-y-4 text-xs">
                  <div className="p-4 rounded-2xl glass-panel space-y-2 border border-violet-200 dark:border-violet-800">
                    <div className="font-semibold text-sm text-violet-700 dark:text-violet-300 flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      <span>{studyPlan.subject} — {studyPlan.total_weeks || 4}-Week Master Study Plan</span>
                    </div>
                    {studyPlan.exam_revision_strategy && (
                      <p className="text-xs text-[var(--text-secondary)]">
                        <strong>Strategy: </strong> {studyPlan.exam_revision_strategy}
                      </p>
                    )}
                  </div>

                  {Array.isArray(studyPlan.weekly_plan) && studyPlan.weekly_plan.map((wk: any, idx: number) => (
                    <div key={idx} className="p-3.5 rounded-xl glass-panel space-y-2 border border-[var(--border-light)]">
                      <div className="font-semibold text-xs text-[var(--text-primary)] flex justify-between">
                        <span>Week {wk.week_number || idx + 1}: {wk.theme}</span>
                        {wk.recommended_hours && <span className="text-violet-500">{wk.recommended_hours} hrs/wk</span>}
                      </div>
                      {wk.learning_objectives && (
                        <div className="text-[11px] text-[var(--text-secondary)]">
                          <strong>Objectives: </strong> {Array.isArray(wk.learning_objectives) ? wk.learning_objectives.join("; ") : wk.learning_objectives}
                        </div>
                      )}
                      {wk.key_activities && (
                        <div className="text-[11px] text-[var(--text-muted)]">
                          <strong>Key Tasks: </strong> {Array.isArray(wk.key_activities) ? wk.key_activities.join(" • ") : wk.key_activities}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
