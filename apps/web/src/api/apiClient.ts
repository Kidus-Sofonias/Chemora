import type {
  AnswerResult,
  ChemistryExploreResult,
  CurrentUser,
  ElementDetail,
  ElementListResult,
  LearningProgress,
  LessonDetail,
  LessonListResult,
  SessionResponse,
  TutorResponse,
  TutorTurn,
} from './types';


const DEFAULT_API_BASE_URL = 'http://localhost:8000';

/**
 * Resolve the Chemora backend base URL from configuration.
 * Frontend environment variables are public (not secrets).
 * A trailing slash is stripped for consistent URL building.
 */
export function resolveApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const url = typeof raw === 'string' ? raw.trim() : '';
  return url ? url.replace(/\/+$/, '') : DEFAULT_API_BASE_URL;
}

/**
 * A typed error surfaced by the API client.
 * - `status` is the HTTP status code when the backend responded.
 * - `status` is `null` when the request failed before an HTTP response
 *   (network unavailable, timeout, DNS failure, backend down).
 */
export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string | null;

  constructor(message: string, status: number | null, code: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }

  /** True when the backend rejected the request as unauthenticated. */
  get isAuthError(): boolean {
    return this.status === 401;
  }

  /** True when the request never reached the backend (no HTTP response). */
  get isNetworkError(): boolean {
    return this.status === null;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
}

/**
 * Centralized API client. All authentication requests go through this client
 * so that base URL, credentials handling, JSON encoding, and error
 * classification live in exactly one place.
 */
export class ApiClient {
  readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl ?? resolveApiBaseUrl();
  }

  /** POST /api/v1/auth/google — exchange a Google credential for a Chemora session. */
  async googleLogin(credential: string): Promise<SessionResponse> {
    return this.request<SessionResponse>('/api/v1/auth/google', {
      method: 'POST',
      body: { credential },
    });
  }

  /** GET /api/v1/auth/me — the backend is the source of truth for the user. */
  async getCurrentUser(): Promise<CurrentUser> {
    return this.request<CurrentUser>('/api/v1/auth/me');
  }

  /** POST /api/v1/auth/logout — revoke the server-side session. */
  async logout(): Promise<void> {
    await this.request<unknown>('/api/v1/auth/logout', { method: 'POST' });
  }

  /**
   * POST /api/v1/chemistry/explore — analyse a formula, SMILES, InChI, or
   * common name through ChemEngine via the backend.
   */
  async exploreChemistry(input: string): Promise<ChemistryExploreResult> {
    return this.request<ChemistryExploreResult>('/api/v1/chemistry/explore', {
      method: 'POST',
      body: { input },
    });
  }

  /** GET /api/v1/elements — periodic-table metadata for all 118 elements. */
  async getElements(): Promise<ElementListResult> {
    return this.request<ElementListResult>('/api/v1/elements');
  }

  /** GET /api/v1/elements/{id} — element detail + computed electron structure. */
  async getElement(identifier: string): Promise<ElementDetail> {
    return this.request<ElementDetail>(
      `/api/v1/elements/${encodeURIComponent(identifier.trim())}`,
    );
  }

  /** GET /api/v1/learning/lessons — the lesson catalog. */
  async getLessons(): Promise<LessonListResult> {
    return this.request<LessonListResult>('/api/v1/learning/lessons');
  }

  /** GET /api/v1/learning/lessons/{slug} — one lesson with sections/questions. */
  async getLesson(slug: string): Promise<LessonDetail> {
    return this.request<LessonDetail>(
      `/api/v1/learning/lessons/${encodeURIComponent(slug)}`,
    );
  }

  /** GET /api/v1/learning/lessons/{slug}/progress — authenticated progress. */
  async getLessonProgress(slug: string): Promise<LearningProgress> {
    return this.request<LearningProgress>(
      `/api/v1/learning/lessons/${encodeURIComponent(slug)}/progress`,
    );
  }

  /** GET /api/v1/learning/progress — progress across all started lessons. */
  async getAllLessonProgress(): Promise<{ progress: LearningProgress[] }> {
    return this.request<{ progress: LearningProgress[] }>('/api/v1/learning/progress');
  }

  /** POST /api/v1/learning/lessons/{slug}/sections/{id}/complete */
  async completeLessonSection(slug: string, sectionId: string): Promise<LearningProgress> {
    return this.request<LearningProgress>(
      `/api/v1/learning/lessons/${encodeURIComponent(slug)}/sections/${encodeURIComponent(
        sectionId,
      )}/complete`,
      { method: 'POST' },
    );
  }

  /**
   * POST /api/v1/learning/lessons/{slug}/answers — validate an answer
   * server-side. The correct answer never reaches the client.
   */
  async submitLessonAnswer(
    slug: string,
    questionId: string,
    answer: string,
  ): Promise<AnswerResult> {
    return this.request<AnswerResult>(
      `/api/v1/learning/lessons/${encodeURIComponent(slug)}/answers`,
      { method: 'POST', body: { question_id: questionId, answer } },
    );
  }

  /**
   * POST /api/v1/learning/tutor — ask the AI chemistry tutor a question.
   * The backend composes the answer (lesson context + ChemEngine tools +
   * AI provider); the client never contacts a provider itself.
   */
  async askTutor(
    message: string,
    history: TutorTurn[] = [],
    lessonSlug?: string,
  ): Promise<TutorResponse> {
    return this.request<TutorResponse>('/api/v1/learning/tutor', {
      method: 'POST',
      body: {
        message,
        history,
        ...(lessonSlug ? { lesson_slug: lessonSlug } : {}),
      },
    });
  }


  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    let response: Response;
    try {
      response = await fetch(this.baseUrl + path, {
        method: options.method ?? 'GET',
        headers:
          options.body === undefined
            ? undefined
            : { 'Content-Type': 'application/json' },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        // Send/receive the HttpOnly session cookie. The browser manages the
        // cookie; JavaScript never reads its value.
        credentials: 'include',
      });
    } catch {
      // Transport-level failure — the backend never answered.
      throw new ApiError(
        'Could not reach the Chemora server. Check your connection and try again.',
        null,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text) as unknown;
      } catch {
        data = null;
      }
    }

    if (!response.ok) {
      const detail = readError(data);
      throw new ApiError(
        detail.message ?? `Request failed (${response.status}).`,
        response.status,
        detail.code,
      );
    }

    return data as T;
  }
}

interface ErrorDetail {
  message: string | null;
  code: string | null;
}

/**
 * Extract a user-facing message and machine code from an error body.
 * Handles both `{detail: "..."}` (auth style) and `{detail: {code, message}}`
 * / `{error: {code, message}}` (chemistry style).
 */
function readError(data: unknown): ErrorDetail {
  if (typeof data !== 'object' || data === null) {
    return { message: null, code: null };
  }
  const record = data as Record<string, unknown>;
  const rawDetail = record.detail;

  if (typeof rawDetail === 'string' && rawDetail) {
    return { message: rawDetail, code: null };
  }
  if (typeof rawDetail === 'object' && rawDetail !== null) {
    const detail = rawDetail as Record<string, unknown>;
    return {
      message: typeof detail.message === 'string' ? detail.message : null,
      code: typeof detail.code === 'string' ? detail.code : null,
    };
  }
  if (typeof record.error === 'object' && record.error !== null) {
    const error = record.error as Record<string, unknown>;
    return {
      message: typeof error.message === 'string' ? error.message : null,
      code: typeof error.code === 'string' ? error.code : null,
    };
  }
  return { message: null, code: null };
}