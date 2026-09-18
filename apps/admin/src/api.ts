// API client for the Chemora admin content management backend.
//
// Follows the same conventions as apps/web/src/api/client.ts:
// - credentials: 'include' for session cookies
// - JSON request/response
// - 401 vs network error classification

import type {
  AdminLesson,
  AdminLessonList,
  AdminLessonUpsert,
  PreviewLesson,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`API error ${status}`);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Lessons ---

export async function listLessons(): Promise<AdminLessonList> {
  return request<AdminLessonList>('/api/v1/admin/lessons');
}

export async function getLesson(slug: string): Promise<AdminLesson> {
  return request<AdminLesson>(`/api/v1/admin/lessons/${slug}`);
}

export async function createLesson(
  payload: AdminLessonUpsert,
): Promise<AdminLesson> {
  return request<AdminLesson>('/api/v1/admin/lessons', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateLesson(
  slug: string,
  payload: AdminLessonUpsert,
): Promise<AdminLesson> {
  return request<AdminLesson>(`/api/v1/admin/lessons/${slug}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function publishLesson(slug: string): Promise<AdminLesson> {
  return request<AdminLesson>(`/api/v1/admin/lessons/${slug}/publish`, {
    method: 'POST',
  });
}

export async function unpublishLesson(slug: string): Promise<AdminLesson> {
  return request<AdminLesson>(`/api/v1/admin/lessons/${slug}/unpublish`, {
    method: 'POST',
  });
}

/**
 * Delete a lesson. By default the backend refuses when student progress
 * references the lesson (409 lesson_has_progress); pass force=true to
 * confirm the destructive action.
 */
export async function deleteLesson(
  slug: string,
  { force = false }: { force?: boolean } = {},
): Promise<void> {
  return request<void>(
    `/api/v1/admin/lessons/${slug}${force ? '?force=true' : ''}`,
    { method: 'DELETE' },
  );
}

export async function previewLesson(slug: string): Promise<PreviewLesson> {
  return request<PreviewLesson>(`/api/v1/admin/lessons/${slug}/preview`);
}

// --- Auth ---

export async function getCurrentUser(): Promise<{
  id: string;
  email: string;
  display_name: string | null;
  is_admin: boolean;
}> {
  return request('/api/v1/auth/me');
}
