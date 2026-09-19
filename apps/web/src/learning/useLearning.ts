import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, type ApiClient } from '../api/apiClient';
import type {
  AnswerResult,
  ChemistryExploreResult,
  ElementDetail,
  LearningProgress,
  LessonDetail,
  LessonSummary,
} from '../api/types';

/**
 * Learning Core state machine (M24).
 *
 * The catalog loads once; opening a lesson fetches the lesson detail plus the
 * authenticated user's progress. `chemistry_spotlight` sections name either an
 * element or a molecule, and the client fetches the corresponding live
 * ChemEngine-computed result from the existing element API or chemistry explore
 * API (cached per session). Answer validation and progress
 * recording always go through the backend — the client never grades answers
 * itself and never sees answer keys.
 *
 * Errors are classified: network failure (backend unreachable) is distinct
 * from API/server errors. Nothing retries automatically (no loops).
 */
export type CatalogState =
  | { kind: 'loading' }
  | { kind: 'error'; network: boolean; message: string }
  | { kind: 'ready'; lessons: LessonSummary[] };

/** Per-lesson progress for the catalog (resume support, M28). */
export type CatalogProgress = Record<string, LearningProgress>;

/** Everything rendered for an open lesson. */
export interface ActiveLesson {
  lesson: LessonDetail;
  progress: LearningProgress | null;
  /** Engine-computed element details for spotlight sections, by symbol. */
  spotlight: Record<string, ElementDetail>;
  spotlightLoading: Record<string, boolean>;
  /** Engine-computed molecule analyses, keyed by the section's input string. */
  molecules: Record<string, ChemistryExploreResult>;
  moleculeLoading: Record<string, boolean>;
  /** User-facing note when a molecule spotlight could not be computed. */
  moleculeError: Record<string, string>;
  /** Graded results per question id, returned by the server. */
  answers: Record<string, AnswerResult>;
  /** Section id with a completion request in flight. */
  completing: string | null;
  /** Question id with an answer submission in flight. */
  answering: string | null;
}

export type LessonState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ready'; active: ActiveLesson }
  | { kind: 'error'; network: boolean; message: string };

const NETWORK_MESSAGE =
  'Cannot reach the Chemora server. Check your connection and try again.';
const SERVER_MESSAGE =
  'The learning service hit a problem. Please try again in a moment.';

/**
 * Only structured backend errors (`detail.code` + `detail.message`) carry a
 * message intended for users; a raw string detail is an unexpected internal
 * error and is replaced by a generic fallback so internals never reach the UI.
 */
export function userFacingMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.isNetworkError) {
      return NETWORK_MESSAGE;
    }
    if (err.code !== null && err.message) {
      return err.message;
    }
  }
  return fallback;
}

function classify(err: unknown): { network: boolean; message: string } {
  return {
    network: err instanceof ApiError && err.isNetworkError,
    message: userFacingMessage(err, SERVER_MESSAGE),
  };
}

/** Apply a mutation to the active lesson if one is open. */
function patchActive(
  prev: LessonState,
  mutate: (active: ActiveLesson) => void,
): LessonState {
  if (prev.kind !== 'ready') {
    return prev;
  }
  const active: ActiveLesson = {
    ...prev.active,
    spotlight: { ...prev.active.spotlight },
    spotlightLoading: { ...prev.active.spotlightLoading },
    molecules: { ...prev.active.molecules },
    moleculeLoading: { ...prev.active.moleculeLoading },
    moleculeError: { ...prev.active.moleculeError },
    answers: { ...prev.active.answers },
    progress: prev.active.progress,
  };
  mutate(active);
  return { kind: 'ready', active };
}

export function useLearning(api: ApiClient) {
  const [catalog, setCatalog] = useState<CatalogState>({ kind: 'loading' });
  const [progressBySlug, setProgressBySlug] = useState<CatalogProgress>({});
  const [current, setCurrent] = useState<LessonState>({ kind: 'idle' });
  const elementCache = useRef(new Map<string, ElementDetail>());
  const moleculeCache = useRef(new Map<string, ChemistryExploreResult>());
  const requestId = useRef(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getLessons()
      .then((result) => {
        if (cancelled) {
          return;
        }
        setCatalog({ kind: 'ready', lessons: result.lessons });
        // Resume support (M28): fetch progress for every started lesson.
        // Best-effort — a failure here leaves the catalog fully usable.
        api
          .getAllLessonProgress()
          .then((all) => {
            if (!cancelled) {
              setProgressBySlug(
                Object.fromEntries(all.progress.map((p) => [p.lesson_slug, p])),
              );
            }
          })
          .catch(() => {
            /* catalog stays usable without progress badges */
          });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setCatalog({ kind: 'error', ...classify(err) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [api]);

  const loadSpotlight = useCallback(
    (symbol: string) => {
      const cached = elementCache.current.get(symbol);
      if (cached) {
        setCurrent((prev) =>
          patchActive(prev, (a) => {
            a.spotlight[symbol] = cached;
          }),
        );
        return;
      }
      setCurrent((prev) =>
        patchActive(prev, (a) => {
          a.spotlightLoading[symbol] = true;
        }),
      );
      void api
        .getElement(symbol)
        .then((detail) => {
          elementCache.current.set(symbol, detail);
          setCurrent((prev) =>
            patchActive(prev, (a) => {
              a.spotlight[symbol] = detail;
              delete a.spotlightLoading[symbol];
            }),
          );
        })
        .catch(() => {
          // A spotlight element that fails to load degrades to prose only;
          // the lesson text is still fully usable.
          setCurrent((prev) =>
            patchActive(prev, (a) => {
              delete a.spotlightLoading[symbol];
            }),
          );
        });
    },
    [api],
  );

  const loadMolecule = useCallback(
    (input: string) => {
      const cached = moleculeCache.current.get(input);
      if (cached) {
        setCurrent((prev) =>
          patchActive(prev, (a) => {
            a.molecules[input] = cached;
          }),
        );
        return;
      }
      setCurrent((prev) =>
        patchActive(prev, (a) => {
          a.moleculeLoading[input] = true;
        }),
      );
      void api
        .exploreChemistry(input)
        .then((result) => {
          moleculeCache.current.set(input, result);
          setCurrent((prev) =>
            patchActive(prev, (a) => {
              a.molecules[input] = result;
              delete a.moleculeLoading[input];
            }),
          );
        })
        .catch((err: unknown) => {
          // A molecule that cannot be analysed degrades to prose plus a
          // user-facing note; the lesson text stays fully usable.
          const message = userFacingMessage(
            err,
            'Could not analyse this molecule right now.',
          );
          setCurrent((prev) =>
            patchActive(prev, (a) => {
              delete a.moleculeLoading[input];
              a.moleculeError[input] = message;
            }),
          );
        });
    },
    [api],
  );

  const openLesson = useCallback(
    async (slug: string) => {
      const id = ++requestId.current;
      setCurrent({ kind: 'loading' });
      try {
        const lesson = await api.getLesson(slug);
        if (id !== requestId.current) {
          return;
        }
        let progress: LearningProgress | null = null;
        try {
          progress = await api.getLessonProgress(slug);
        } catch {
          // Progress is an enhancement; a lesson can be read without it.
          progress = null;
        }
        if (id !== requestId.current) {
          return;
        }
        const active: ActiveLesson = {
          lesson,
          progress,
          spotlight: {},
          spotlightLoading: {},
          molecules: {},
          moleculeLoading: {},
          moleculeError: {},
          answers: {},
          completing: null,
          answering: null,
        };
        setCurrent({ kind: 'ready', active });
        for (const section of lesson.sections) {
          if (section.kind !== 'chemistry_spotlight') {
            continue;
          }
          if (section.element_symbol) {
            loadSpotlight(section.element_symbol);
          }
          if (section.molecule_input) {
            loadMolecule(section.molecule_input);
          }
        }
      } catch (err) {
        if (id !== requestId.current) {
          return; // a newer request superseded this one
        }
        setCurrent({ kind: 'error', ...classify(err) });
      }
    },
    [api, loadSpotlight, loadMolecule],
  );

  const backToCatalog = useCallback(() => {
    setCurrent({ kind: 'idle' });
  }, []);

  /** Update the catalog's cached progress after in-lesson changes. */
  const noteProgress = useCallback((progress: LearningProgress | null) => {
    if (!progress) {
      return;
    }
    setProgressBySlug((prev) => ({ ...prev, [progress.lesson_slug]: progress }));
  }, []);

  const completeSection = useCallback(
    async (slug: string, sectionId: string) => {
      setCurrent((prev) =>
        patchActive(prev, (a) => {
          a.completing = sectionId;
        }),
      );
      try {
        const progress = await api.completeLessonSection(slug, sectionId);
        noteProgress(progress);
        setCurrent((prev) =>
          patchActive(prev, (a) => {
            a.progress = progress;
            a.completing = null;
          }),
        );
      } catch (err) {
        setCurrent((prev) =>
          patchActive(prev, (a) => {
            a.completing = null;
          }),
        );
        throw err;
      }
    },
    [api],
  );

  const submitAnswer = useCallback(
    async (slug: string, questionId: string, answer: string) => {
      setCurrent((prev) =>
        patchActive(prev, (a) => {
          a.answering = questionId;
        }),
      );
      try {
        const result = await api.submitLessonAnswer(slug, questionId, answer);
        noteProgress(result.progress);
        setCurrent((prev) =>
          patchActive(prev, (a) => {
            a.answers[questionId] = result;
            a.progress = result.progress;
            a.answering = null;
          }),
        );
        return result;
      } catch (err) {
        setCurrent((prev) =>
          patchActive(prev, (a) => {
            a.answering = null;
          }),
        );
        throw err;
      }
    },
    [api],
  );

  return {
    catalog,
    progressBySlug,
    current,
    openLesson,
    backToCatalog,
    completeSection,
    submitAnswer,
  };
}

