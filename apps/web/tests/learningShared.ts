/** Shared fixtures and default fake-backend handler for learning tests. */
import { jsonResponse, fakeUser } from './helpers';

export const catalog = {
  lessons: [
    {
      id: 'lesson-electron-configuration',
      slug: 'electron-configuration',
      title: 'Electron Configurations',
      description: 'How electrons arrange themselves around a nucleus.',
      subject: 'atomic structure',
      difficulty: 'beginner',
      estimated_minutes: 8,
      section_count: 5,
      question_count: 2,
    },
    {
      id: 'lesson-valence-electrons',
      slug: 'valence-electrons',
      title: 'Valence Electrons',
      description: 'The outermost electrons do the chemistry.',
      subject: 'atomic structure',
      difficulty: 'beginner',
      estimated_minutes: 6,
      section_count: 4,
      question_count: 1,
    },
    {
      id: 'lesson-chemical-formulas',
      slug: 'chemical-formulas',
      title: 'Chemical Formulas',
      description: 'What a formula tells you.',
      subject: 'chemical formulas',
      difficulty: 'beginner',
      estimated_minutes: 9,
      section_count: 5,
      question_count: 2,
    },
  ],
};

export const oxygenDetail = {
  atomic_number: 8,
  symbol: 'O',
  name: 'Oxygen',
  atomic_mass: 15.999,
  period: 2,
  group: 16,
  block: 'p',
  category: 'nonmetal',
  config_full: '1s2 2s2 2p4',
  config_shorthand: '[He] 2s2 2p4',
  noble_gas: 'He',
  valence_electrons: 6,
  core_electrons: 2,
  unpaired_electrons: 2,
  shells: { '1': 2, '2': 6 },
  subshells: { '1s': 2, '2s': 2, '2p': 4 },
  orbitals: [
    { orbital: '1s', electrons: 2, capacity: 2, subshell: 's', shell: 1 },
    { orbital: '2s', electrons: 2, capacity: 2, subshell: 's', shell: 2 },
    { orbital: '2p', electrons: 4, capacity: 6, subshell: 'p', shell: 2 },
  ],
  explanation: 'Electron Configuration of Oxygen (O, Z=8)',
};

export const lessonDetail = {
  id: 'lesson-electron-configuration',
  slug: 'electron-configuration',
  title: 'Electron Configurations',
  description: 'How electrons arrange themselves around a nucleus.',
  subject: 'atomic structure',
  difficulty: 'beginner',
  estimated_minutes: 8,
  sections: [
    {
      id: 'intro',
      kind: 'introduction',
      title: 'Why arrangements matter',
      body: ['Every atom contains electrons.'],
      element_symbol: null,
      molecule_input: null,
      questions: [],
    },
    {
      id: 'spotlight',
      kind: 'chemistry_spotlight',
      title: 'See it live',
      body: ['Pick an element below.'],
      element_symbol: 'O',
      molecule_input: null,
      questions: [],
    },
    {
      id: 'practice',
      kind: 'practice',
      title: 'Check your understanding',
      body: [],
      element_symbol: null,
      molecule_input: null,
      questions: [
        {
          id: 'ec-1',
          kind: 'numeric',
          prompt: 'How many electrons can a single 2p subshell hold at most?',
          options: [],
        },
        {
          id: 'ec-2',
          kind: 'multiple_choice',
          prompt: 'Which rule says degenerate orbitals fill singly before pairing?',
          options: ['Aufbau principle', "Hund's rule", 'Pauli exclusion principle'],
        },
      ],
    },
  ],
};

export const freshProgress = {
  lesson_slug: 'electron-configuration',
  completed_sections: [],
  answers: {},
  progress_percent: 0,
  completed: false,
};

export const moleculeLessonDetail = {
  id: 'lesson-chemical-formulas',
  slug: 'chemical-formulas',
  title: 'Chemical Formulas',
  description: 'What a formula tells you.',
  subject: 'chemical formulas',
  difficulty: 'beginner',
  estimated_minutes: 9,
  sections: [
    {
      id: 'intro',
      kind: 'introduction',
      title: 'A formula is a count, not a map',
      body: ['A chemical formula tells you which elements are present.'],
      element_symbol: null,
      molecule_input: null,
      questions: [],
    },
    {
      id: 'spotlight',
      kind: 'chemistry_spotlight',
      title: 'Analyse a formula live',
      body: ['The engine parses the formula below.'],
      element_symbol: null,
      molecule_input: 'H2O',
      questions: [],
    },
    {
      id: 'practice',
      kind: 'practice',
      title: 'Check your understanding',
      body: [],
      element_symbol: null,
      molecule_input: null,
      questions: [
        {
          id: 'fm-1',
          kind: 'formula',
          prompt:
            'Which chemical formula represents a molecule with two hydrogen atoms and one oxygen atom?',
          options: [],
        },
      ],
    },
  ],
};

export const waterResult = {
  input: 'H2O',
  detected_type: 'formula',
  structure_available: false,
  identity: {
    formula: 'H2O',
    exact_mass: 18.0106,
    average_mass: 18.015,
    heavy_atom_count: 1,
    atom_count: 3,
  },
  structure: null,
  properties: null,
};

export async function defaultHandler(
  _method: string,
  url: string,
  body: unknown,
): Promise<Response> {
  if (url.endsWith('/auth/me')) return jsonResponse(200, fakeUser);
  if (url.endsWith('/learning/lessons')) return jsonResponse(200, catalog);
  if (url.includes('/learning/lessons/electron-configuration/progress')) {
    return jsonResponse(200, freshProgress);
  }
  if (url.endsWith('/learning/lessons/electron-configuration')) {
    return jsonResponse(200, lessonDetail);
  }
  if (url.endsWith('/chemistry/explore')) {
    const submission = body as { input: string };
    return jsonResponse(200, { ...waterResult, input: submission.input });
  }
  if (url.includes('/learning/lessons/chemical-formulas/progress')) {
    return jsonResponse(200, { ...freshProgress, lesson_slug: 'chemical-formulas' });
  }
  if (url.includes('/learning/lessons/chemical-formulas/answers')) {
    const submission = body as { question_id: string; answer: string };
    // Mirrors the backend: equivalent spellings canonicalize to the same
    // formula, so both are graded correct.
    const correct = submission.answer === 'H2O' || submission.answer === 'HOH';
    return jsonResponse(200, {
      question_id: submission.question_id,
      correct,
      explanation: 'The engine canonicalizes both spellings to H2O.',
      progress: {
        ...freshProgress,
        lesson_slug: 'chemical-formulas',
        answers: { [submission.question_id]: correct },
      },
    });
  }
  if (url.endsWith('/learning/lessons/chemical-formulas')) {
    return jsonResponse(200, moleculeLessonDetail);
  }
  if (url.endsWith('/elements/O')) return jsonResponse(200, oxygenDetail);
  if (url.includes('/learning/lessons/electron-configuration/answers')) {
    const submission = body as { question_id: string; answer: string };
    const correct =
      submission.question_id === 'ec-1'
        ? submission.answer === '6'
        : submission.answer === "Hund's rule";
    return jsonResponse(200, {
      question_id: submission.question_id,
      correct,
      explanation: 'The engine says so — see the orbital diagram above.',
      progress: {
        ...freshProgress,
        answers: { [submission.question_id]: correct },
      },
    });
  }
  return jsonResponse(404, { detail: 'not found' });
}
