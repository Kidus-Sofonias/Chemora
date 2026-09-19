import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../src/App';
import * as api from '../src/api';
import type { AdminLessonList, AdminLesson, PreviewLesson } from '../src/types';

// --- Mock data (hoisted with vi.hoisted so vi.mock can reference them) ---

const { mockListLessons, mockLesson, mockPreview, apiMocks } = vi.hoisted(
  () => {
    const mockListLessons: AdminLessonList = {
      lessons: [
        {
          slug: 'electron-configuration',
          title: 'Electron Configurations',
          topic: 'atomic structure',
          difficulty: 'beginner',
          estimated_minutes: 8,
          ordering: 1,
          published: true,
          section_count: 5,
          question_count: 2,
          updated_at: '2026-09-18T00:00:00Z',
        },
        {
          slug: 'chemical-formulas',
          title: 'Chemical Formulas',
          topic: 'chemical formulas',
          difficulty: 'beginner',
          estimated_minutes: 9,
          ordering: 4,
          published: false,
          section_count: 5,
          question_count: 2,
          updated_at: '2026-09-17T00:00:00Z',
        },
      ],
    };

    const mockLesson: AdminLesson = {
      slug: 'electron-configuration',
      title: 'Electron Configurations',
      description: 'How electrons arrange themselves.',
      topic: 'atomic structure',
      difficulty: 'beginner',
      estimated_minutes: 8,
      ordering: 1,
      published: true,
      published_at: '2026-09-18T00:00:00Z',
      created_at: '2026-09-10T00:00:00Z',
      updated_at: '2026-09-18T00:00:00Z',
      sections: [
        {
          id: 'intro',
          kind: 'introduction',
          title: 'Why arrangements matter',
          body: ['Every atom contains electrons.'],
          element_symbol: null,
          molecule_input: null,
          ordering: 1,
          questions: [],
        },
        {
          id: 'spotlight',
          kind: 'chemistry_spotlight',
          title: 'See it live',
          body: ['Watch the engine compute.'],
          element_symbol: 'O',
          molecule_input: null,
          ordering: 2,
          questions: [],
        },
      ],
    };

    const mockPreview: PreviewLesson = {
      id: 'electron-configuration',
      slug: 'electron-configuration',
      title: 'Electron Configurations',
      description: 'How electrons arrange themselves.',
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
      ],
    };

    const apiMocks = {
      listLessons: vi.fn().mockResolvedValue(mockListLessons),
      getLesson: vi.fn().mockResolvedValue(mockLesson),
      createLesson: vi.fn().mockResolvedValue(mockLesson),
      updateLesson: vi.fn().mockResolvedValue(mockLesson),
      publishLesson: vi.fn().mockResolvedValue(mockLesson),
      unpublishLesson: vi.fn().mockResolvedValue(mockLesson),
      deleteLesson: vi.fn().mockResolvedValue(undefined),
      previewLesson: vi.fn().mockResolvedValue(mockPreview),
      getCurrentUser: vi.fn().mockResolvedValue({
        id: '1',
        email: 'admin@test.com',
        display_name: 'Admin',
        is_admin: true,
      }),
    };

    return { mockListLessons, mockLesson, mockPreview, apiMocks };
  },
);

vi.mock('../src/api', () => ({
  ApiError: class extends Error {
    status: number;
    body: unknown;
    constructor(status: number, body: unknown) {
      super(`API error ${status}`);
      this.status = status;
      this.body = body;
    }
  },
  listLessons: (...args: unknown[]) => apiMocks.listLessons(...args),
  getLesson: (...args: unknown[]) => apiMocks.getLesson(...args),
  createLesson: (...args: unknown[]) => apiMocks.createLesson(...args),
  updateLesson: (...args: unknown[]) => apiMocks.updateLesson(...args),
  publishLesson: (...args: unknown[]) => apiMocks.publishLesson(...args),
  unpublishLesson: (...args: unknown[]) => apiMocks.unpublishLesson(...args),
  deleteLesson: (...args: unknown[]) => apiMocks.deleteLesson(...args),
  previewLesson: (...args: unknown[]) => apiMocks.previewLesson(...args),
  getCurrentUser: (...args: unknown[]) => apiMocks.getCurrentUser(...args),
}));

beforeEach(() => {
  window.location.hash = '/dashboard';
  vi.clearAllMocks();
  // Reset mock return values
  apiMocks.listLessons.mockResolvedValue(mockListLessons);
  apiMocks.getLesson.mockResolvedValue(mockLesson);
  apiMocks.createLesson.mockResolvedValue(mockLesson);
  apiMocks.updateLesson.mockResolvedValue(mockLesson);
  apiMocks.publishLesson.mockResolvedValue(mockLesson);
  apiMocks.unpublishLesson.mockResolvedValue(mockLesson);
  apiMocks.deleteLesson.mockResolvedValue(undefined);
  apiMocks.previewLesson.mockResolvedValue(mockPreview);
  apiMocks.getCurrentUser.mockResolvedValue({
    id: '1',
    email: 'admin@test.com',
    display_name: 'Admin',
    is_admin: true,
  });
});

// --- Tests ---

describe('Admin CMS', () => {
  it('renders the dashboard with lesson stats', async () => {
    render(<App />);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Dashboard' }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('2')).toBeInTheDocument();
    // '1' appears in the Published stat (and possibly elsewhere), so assert
    // via the stat cards rather than a bare text match.
    const statCards = screen.getAllByText(/^(1|2)$/);
    expect(statCards.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Total Lessons')).toBeInTheDocument();
    expect(screen.getByText('Drafts')).toBeInTheDocument();
  });

  it('navigates to lesson list', async () => {
    render(<App />);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Dashboard' }),
      ).toBeInTheDocument();
    });
    const user = userEvent.setup();
    await user.click(screen.getByText('View All Lessons'));
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Lessons' }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Electron Configurations')).toBeInTheDocument();
    expect(screen.getByText('Chemical Formulas')).toBeInTheDocument();
  });

  it('shows published/draft badges correctly', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(screen.getAllByText('Published').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('Draft').length).toBeGreaterThan(0);
  });

  it('shows publish/unpublish buttons based on status', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Unpublish' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Publish' })).toBeInTheDocument();
  });

  it('navigates to lesson editor for existing lesson', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText('Electron Configurations')).toBeInTheDocument();
    });
    const user = userEvent.setup();
    const editButtons = screen.getAllByRole('button', { name: 'Edit' });
    await user.click(editButtons[0]);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Edit Lesson' }),
      ).toBeInTheDocument();
    });
  });

  it('navigates to new lesson editor', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Lessons' }),
      ).toBeInTheDocument();
    });
    const user = userEvent.setup();
    await user.click(screen.getByText('+ New Lesson'));
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'New Lesson' }),
      ).toBeInTheDocument();
    });
  });

  it('renders preview page', async () => {
    window.location.hash = '/lessons/electron-configuration/preview';
    render(<App />);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', {
          name: 'Preview: Electron Configurations',
        }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Preview Mode')).toBeInTheDocument();
    expect(
      screen.getByText('Every atom contains electrons.'),
    ).toBeInTheDocument();
  });

  it('preview does not show answer keys', async () => {
    window.location.hash = '/lessons/electron-configuration/preview';
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText('Preview Mode')).toBeInTheDocument();
    });
    expect(screen.queryByText('correct')).not.toBeInTheDocument();
  });

  it('deletes a lesson after confirmation', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Lessons' }),
      ).toBeInTheDocument();
    });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = userEvent.setup();
    await user.click(screen.getAllByRole('button', { name: 'Delete' })[0]);
    await waitFor(() => {
      expect(apiMocks.deleteLesson).toHaveBeenCalledWith('electron-configuration');
    });
    confirmSpy.mockRestore();
  });

  it('does not delete when confirmation is cancelled', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Lessons' }),
      ).toBeInTheDocument();
    });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const user = userEvent.setup();
    await user.click(screen.getAllByRole('button', { name: 'Delete' })[0]);
    expect(apiMocks.deleteLesson).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('forces deletion after a 409 progress conflict', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Lessons' }),
      ).toBeInTheDocument();
    });
    // Must be the mocked module's ApiError so the instanceof check in App matches.
    apiMocks.deleteLesson.mockRejectedValueOnce(new api.ApiError(409, {
      code: 'lesson_has_progress',
      message: 'progress exists',
    }));
    const confirmSpy = vi
      .spyOn(window, 'confirm')
      .mockReturnValueOnce(true) // initial delete confirmation
      .mockReturnValueOnce(true); // force confirmation
    const user = userEvent.setup();
    await user.click(screen.getAllByRole('button', { name: 'Delete' })[0]);
    await waitFor(() => {
      expect(apiMocks.deleteLesson).toHaveBeenCalledWith('electron-configuration', {
        force: true,
      });
    });
    confirmSpy.mockRestore();
  });
});

describe('Admin CMS — M28 chemistry reference authoring', () => {
  it('exposes molecule input authoring for chemistry spotlight sections', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText('Electron Configurations')).toBeInTheDocument();
    });
    const user = userEvent.setup();
    await user.click(screen.getAllByRole('button', { name: 'Edit' })[0]);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Edit Lesson' }),
      ).toBeInTheDocument();
    });
    // The SectionEditor offers Element Symbol and Molecule Input fields for
    // chemistry_spotlight sections so admins can author engine references.
    expect(screen.getByLabelText(/Element Symbol/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Molecule Input/)).toBeInTheDocument();
  });

  it('shows validation feedback when the backend rejects chemistry content', async () => {
    window.location.hash = '/lessons';
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText('Electron Configurations')).toBeInTheDocument();
    });
    const user = userEvent.setup();
    await user.click(screen.getAllByRole('button', { name: 'Edit' })[0]);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Edit Lesson' }),
      ).toBeInTheDocument();
    });
    // Save → backend 422 with per-field chemistry validation errors.
    apiMocks.updateLesson.mockRejectedValueOnce(
      new api.ApiError(422, {
        errors: [
          { field: 'sections', message: "Section 'spotlight' references an unparseable molecule 'Xx999'." },
        ],
      }),
    );
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(screen.getByText(/unparseable molecule/)).toBeInTheDocument();
    });
  });
});
