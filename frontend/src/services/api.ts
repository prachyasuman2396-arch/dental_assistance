const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface CitationItem {
  filename?: string;
  page_number?: number;
  similarity_score?: number;
  title?: string;
  authors?: string;
  journal?: string;
  pub_date?: string;
  pmid?: string;
  doi?: string;
  url?: string;
  evidence_level?: string;
}

export interface CitationsMetadata {
  documents?: CitationItem[];
  research_papers?: CitationItem[];
}

export interface StreamChatEvents {
  onStart?: (data: { conversation_id: string }) => void;
  onStatus?: (data: { status: string; message: string }) => void;
  onCitation?: (data: { citations: CitationsMetadata }) => void;
  onToken?: (data: { token: string; provider?: string; model?: string }) => void;
  onEnd?: (data: {
    conversation_id: string;
    answer: string;
    provider?: string;
    model?: string;
    latency_ms: number;
    citations: CitationsMetadata;
  }) => void;
  onError?: (err: string) => void;
}

export interface UserProfileData {
  preferred_name?: string;
  academic_institution?: string;
  academic_discipline?: string;
  current_level?: string;
  explanation_style?: string;
  learning_goals?: string[];
}

export interface LongTermMemoryItem {
  id: string;
  memory_type: string;
  topic?: string;
  content: string;
  importance: number;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  provider?: string;
  model?: string;
  latency_ms?: number;
  citations?: CitationsMetadata;
  created_at?: string;
}

export interface ConversationItem {
  id: string;
  title: string;
  metadata_json?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StudyDocument {
  id: string;
  filename: string;
  file_size_bytes: number;
  page_count: number;
  status: "pending" | "processing" | "completed" | "failed";
  error_message?: string;
  created_at: string;
}

export type DentalDocument = StudyDocument;

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  difficulty: string;
}

export interface Flashcard {
  question: string;
  answer: string;
  topic: string;
  difficulty: string;
}

class StudyApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("student_token");
    }
  }

  private setToken(tok: string) {
    this.token = tok;
    if (typeof window !== "undefined") {
      localStorage.setItem("student_token", tok);
    }
  }

  private getHeaders(): HeadersInit {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  }

  /**
   * Automatically ensure student authenticated session exists.
   */
  async ensureSession(): Promise<string> {
    if (this.token) return this.token;

    try {
      // Attempt login first
      const loginRes = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "student@university.edu",
          password: "StudentPassword2026!",
        }),
      });

      if (loginRes.ok) {
        const data = await loginRes.json();
        this.setToken(data.access_token);
        return data.access_token;
      }

      // If not registered yet, register
      const regRes = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "student@university.edu",
          password: "StudentPassword2026!",
          full_name: "Student Scholar",
          academic_level: "University Student",
        }),
      });

      if (regRes.ok) {
        const data = await regRes.json();
        this.setToken(data.access_token);
        return data.access_token;
      }
    } catch (e) {
      console.warn("Backend authentication connection attempt failed:", e);
    }

    return "guest_session";
  }

  async checkHealth(): Promise<{ status: string; database?: string; pgvector_extension?: string }> {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      if (res.ok) return await res.json();
    } catch {
      // Server not reachable
    }
    return { status: "offline" };
  }

  async getConversations(): Promise<ConversationItem[]> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/conversations`, {
        headers: this.getHeaders(),
      });
      if (res.ok) return await res.json();
    } catch (e) {
      console.error("Failed to load conversations:", e);
    }
    return [];
  }

  async createConversation(title = "New Study Session"): Promise<ConversationItem | null> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/conversations`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({ title }),
      });
      if (res.ok) return await res.json();
    } catch (e) {
      console.error("Failed to create conversation:", e);
    }
    return null;
  }

  async getMessages(conversationId: string): Promise<ChatMessage[]> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}/messages`, {
        headers: this.getHeaders(),
      });
      if (res.ok) return await res.json();
    } catch (e) {
      console.error("Failed to get messages:", e);
    }
    return [];
  }

  async deleteConversation(conversationId: string): Promise<boolean> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}`, {
        method: "DELETE",
        headers: this.getHeaders(),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  async sendChat(
    message: string,
    conversationId?: string,
    documentId?: string
  ): Promise<{
    conversation_id: string;
    message: string;
    provider?: string;
    model?: string;
    latency_ms: number;
    citations: CitationsMetadata;
  }> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        document_id: documentId,
        stream: false,
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Chat error (${res.status}): ${err}`);
    }

    return await res.json();
  }

  async streamChat(
    message: string,
    conversationId?: string,
    documentId?: string,
    callbacks?: StreamChatEvents,
    abortSignal?: AbortSignal
  ): Promise<void> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        document_id: documentId,
        stream: true,
      }),
      signal: abortSignal,
    });

    if (!res.ok) {
      const err = await res.text();
      callbacks?.onError?.(`Chat error (${res.status}): ${err}`);
      return;
    }

    if (!res.body) {
      callbacks?.onError?.("ReadableStream is not supported on this response");
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let currentEvent = "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            currentEvent = "";
            continue;
          }

          if (trimmed.startsWith("event:")) {
            currentEvent = trimmed.slice(6).trim();
          } else if (trimmed.startsWith("data:")) {
            const rawData = trimmed.slice(5).trim();
            try {
              const payload = JSON.parse(rawData);
              const eventType = currentEvent || payload.type;

              if (eventType === "message_start") {
                callbacks?.onStart?.(payload);
              } else if (eventType === "status") {
                callbacks?.onStatus?.(payload);
              } else if (eventType === "citation") {
                callbacks?.onCitation?.(payload);
              } else if (eventType === "token") {
                callbacks?.onToken?.(payload);
              } else if (eventType === "message_end") {
                callbacks?.onEnd?.(payload);
              } else if (eventType === "error") {
                callbacks?.onError?.(payload.error || "Streaming error");
              }
            } catch {
              // Ignore non-JSON line
            }
          }
        }
      }
    } catch (err: unknown) {
      const e = err as { name?: string; message?: string };
      if (e?.name === "AbortError") {
        console.log("Stream generation aborted by user.");
      } else {
        callbacks?.onError?.(e?.message || "Stream read error");
      }
    } finally {
      reader.releaseLock();
    }
  }

  async getProfile(): Promise<UserProfileData | null> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/profile`, {
        headers: this.getHeaders(),
      });
      if (res.ok) return await res.json();
    } catch (e) {
      console.error("Failed to fetch profile:", e);
    }
    return null;
  }

  async updateProfile(data: UserProfileData): Promise<UserProfileData | null> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/profile`, {
        method: "PUT",
        headers: this.getHeaders(),
        body: JSON.stringify(data),
      });
      if (res.ok) return await res.json();
    } catch (e) {
      console.error("Failed to update profile:", e);
    }
    return null;
  }

  async getMemories(): Promise<LongTermMemoryItem[]> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/memories`, {
        headers: this.getHeaders(),
      });
      if (res.ok) return await res.json();
    } catch (e) {
      console.error("Failed to fetch memories:", e);
    }
    return [];
  }

  async deleteMemory(id: string): Promise<boolean> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/memories/${id}`, {
        method: "DELETE",
        headers: this.getHeaders(),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  async uploadDocument(file: File): Promise<StudyDocument> {
    await this.ensureSession();
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.token}`,
      },
      body: formData,
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Upload failed (${res.status}): ${err}`);
    }

    return await res.json();
  }

  async getDocuments(): Promise<StudyDocument[]> {
    await this.ensureSession();
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/documents`, {
        headers: this.getHeaders(),
      });
      if (res.ok) return await res.json();
    } catch (e) {
      console.error("Failed to fetch documents:", e);
    }
    return [];
  }

  async generateQuiz(topic: string, numQuestions = 3, difficulty = "medium"): Promise<QuizQuestion[]> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/study/quiz`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ topic, num_questions: numQuestions, difficulty }),
    });

    if (!res.ok) throw new Error("Failed to generate quiz");
    return await res.json();
  }

  async generateFlashcards(topic: string, count = 4, difficulty = "medium"): Promise<Flashcard[]> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/study/flashcards`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ topic, count, difficulty }),
    });

    if (!res.ok) throw new Error("Failed to generate flashcards");
    return await res.json();
  }

  async generateViva(topic: string, count = 3, difficulty = "medium"): Promise<any[]> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/study/viva`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ topic, count, difficulty }),
    });

    if (!res.ok) throw new Error("Failed to generate viva questions");
    return await res.json();
  }

  async generateStudyPlan(subject: string, durationWeeks = 4, hoursPerWeek = 10): Promise<any> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/study/plan`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ subject, duration_weeks: durationWeeks, hours_per_week: hoursPerWeek }),
    });

    if (!res.ok) throw new Error("Failed to generate study plan");
    return await res.json();
  }

  async generateRevisionSummary(topic: string): Promise<{ topic: string; summary: string }> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/study/summary`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ topic }),
    });

    if (!res.ok) throw new Error("Failed to generate revision summary");
    return await res.json();
  }

  async generateDerivation(concept: string): Promise<{ concept: string; derivation: string }> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/study/derivation`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ concept }),
    });

    if (!res.ok) throw new Error("Failed to generate derivation");
    return await res.json();
  }

  async generateTopicComparison(topicA: string, topicB: string): Promise<{ topic_a: string; topic_b: string; comparison: string }> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/study/compare`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ topic_a: topicA, topic_b: topicB }),
    });

    if (!res.ok) throw new Error("Failed to generate topic comparison");
    return await res.json();
  }

  async listMcpTools(category?: string): Promise<any[]> {
    await this.ensureSession();
    const url = category
      ? `${API_BASE_URL}/api/v1/mcp/tools?category=${encodeURIComponent(category)}`
      : `${API_BASE_URL}/api/v1/mcp/tools`;
    const res = await fetch(url, { headers: this.getHeaders() });
    if (!res.ok) return [];
    return await res.json();
  }

  async executeMcpTool(toolName: string, args: Record<string, any> = {}, conversationId?: string): Promise<any> {
    await this.ensureSession();
    const res = await fetch(`${API_BASE_URL}/api/v1/mcp/execute`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        tool_name: toolName,
        arguments: args,
        conversation_id: conversationId,
      }),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`MCP tool execution failed (${res.status}): ${err}`);
    }
    return await res.json();
  }
}

export const studyApi = new StudyApiClient();
export const dentalApi = studyApi;
export type DentalApiClient = StudyApiClient;
