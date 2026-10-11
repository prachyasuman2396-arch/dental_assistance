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

export interface DentalDocument {
  id: string;
  filename: string;
  file_size_bytes: number;
  page_count: number;
  status: "pending" | "processing" | "completed" | "failed";
  error_message?: string;
  created_at: string;
}

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

class DentalApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("sristi_token");
    }
  }

  private setToken(tok: string) {
    this.token = tok;
    if (typeof window !== "undefined") {
      localStorage.setItem("sristi_token", tok);
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
   * Automatically ensure Sristi's authenticated session exists.
   */
  async ensureSession(): Promise<string> {
    if (this.token) return this.token;

    try {
      // Attempt login first
      const loginRes = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "sristi.biswal@dental.edu",
          password: "SristiPassword2026!",
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
          email: "sristi.biswal@dental.edu",
          password: "SristiPassword2026!",
          full_name: "Sristi Biswal",
          academic_level: "BDS Dental Scholar",
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

  async uploadDocument(file: File): Promise<DentalDocument> {
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

  async getDocuments(): Promise<DentalDocument[]> {
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
}

export const dentalApi = new DentalApiClient();
