// Types matching the backend admin API schemas.

export interface AdminQuestion {
  id: string;
  kind: string;
  prompt: string;
  correct: string;
  explanation: string;
  options: string[];
  ordering: number;
}

export interface AdminSection {
  id: string;
  kind: string;
  title: string;
  body: string[];
  element_symbol: string | null;
  molecule_input: string | null;
  ordering: number;
  questions: AdminQuestion[];
}

export interface AdminLesson {
  slug: string;
  title: string;
  description: string;
  topic: string;
  difficulty: string;
  estimated_minutes: number;
  ordering: number;
  published: boolean;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  sections: AdminSection[];
}

export interface AdminLessonSummary {
  slug: string;
  title: string;
  topic: string;
  difficulty: string;
  estimated_minutes: number;
  ordering: number;
  published: boolean;
  section_count: number;
  question_count: number;
  updated_at: string | null;
}

export interface AdminLessonList {
  lessons: AdminLessonSummary[];
}

export interface AdminErrorDetail {
  code: string;
  message: string;
  errors?: Array<{ field: string; message: string }>;
}

// Upsert payloads matching backend AdminLessonUpsert.
export interface AdminQuestionUpsert {
  id: string;
  kind: string;
  prompt: string;
  correct: string;
  explanation: string;
  options: string[];
}

export interface AdminSectionUpsert {
  id: string;
  kind: string;
  title: string;
  body: string[];
  element_symbol: string | null;
  molecule_input: string | null;
  questions: AdminQuestionUpsert[];
}

export interface AdminLessonUpsert {
  slug: string;
  title: string;
  description: string;
  subject: string;
  difficulty: string;
  estimated_minutes: number;
  order: number;
  sections: AdminSectionUpsert[];
}

// Preview types (student-safe, no answer keys).
export interface PreviewQuestion {
  id: string;
  kind: string;
  prompt: string;
  options: string[];
}

export interface PreviewSection {
  id: string;
  kind: string;
  title: string;
  body: string[];
  element_symbol: string | null;
  molecule_input: string | null;
  questions: PreviewQuestion[];
}

export interface PreviewLesson {
  id: string;
  slug: string;
  title: string;
  description: string;
  subject: string;
  difficulty: string;
  estimated_minutes: number;
  sections: PreviewSection[];
}
