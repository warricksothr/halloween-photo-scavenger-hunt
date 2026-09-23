import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    adminEvents: vi.fn(),
    adminRiddles: vi.fn(),
    adminCreateRiddle: vi.fn(),
    adminPatchRiddle: vi.fn(),
    adminDeleteRiddle: vi.fn(),
  },
}));

vi.mock('../api', () => ({ api: mocks.api }));

import { AdminRiddles } from './AdminRiddles';

const event = { id: 'ev-1', name: 'Gotham Halloween', status: 'lobby' };
const riddle = (id, text, sort_order) => ({ id, text, sort_order });

describe('admin riddle management', () => {
  beforeEach(() => {
    mocks.api.adminEvents.mockResolvedValue([event]);
    mocks.api.adminRiddles.mockResolvedValue([]);
    mocks.api.adminCreateRiddle.mockResolvedValue({});
    mocks.api.adminPatchRiddle.mockResolvedValue({});
    mocks.api.adminDeleteRiddle.mockResolvedValue({ ok: true });
  });

  function texts(container) {
    return [...container.querySelectorAll('.admin-riddle-body')].map(
      (node) => node.textContent,
    );
  }

  it('lists the selected event\'s riddles in order', async () => {
    mocks.api.adminRiddles.mockResolvedValue([
      riddle('r1', 'I guard the door.', 0),
      riddle('r2', 'Eight legs in the corner.', 1),
    ]);

    const { container } = render(<AdminRiddles />);

    expect(await screen.findByText('I guard the door.')).toBeTruthy();
    expect(mocks.api.adminRiddles).toHaveBeenCalledWith('ev-1');
    expect(texts(container)).toEqual([
      'I guard the door.',
      'Eight legs in the corner.',
    ]);
  });

  it('appends a new riddle past the last sort order', async () => {
    mocks.api.adminRiddles.mockResolvedValue([
      riddle('r1', 'First.', 0),
      riddle('r2', 'Second.', 4),
    ]);

    render(<AdminRiddles />);

    // Wait for the list before adding: the sort order is derived from it.
    await screen.findByText('Second.');
    const textarea = screen.getByLabelText('Add a riddle');
    fireEvent.input(textarea, { target: { value: '  A new clue.  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add to board' }));

    await waitFor(() => {
      expect(mocks.api.adminCreateRiddle).toHaveBeenCalledWith('ev-1', {
        text: 'A new clue.',
        sort_order: 5,
      });
    });
    expect(textarea.value).toBe('');
  });

  it('moves a riddle up by renumbering the rows that changed', async () => {
    const [first, second] = [
      riddle('r1', 'First.', 0),
      riddle('r2', 'Second.', 1),
    ];
    mocks.api.adminRiddles.mockResolvedValue([first, second]);
    mocks.api.adminRiddles
      .mockResolvedValueOnce([first, second])
      .mockResolvedValue([{ ...second, sort_order: 0 }, { ...first, sort_order: 1 }]);

    const { container } = render(<AdminRiddles />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Move riddle 2 up' }),
    );

    await waitFor(() => {
      expect(mocks.api.adminPatchRiddle).toHaveBeenNthCalledWith(1, 'ev-1', 'r2', {
        sort_order: 0,
      });
    });
    expect(mocks.api.adminPatchRiddle).toHaveBeenNthCalledWith(2, 'ev-1', 'r1', {
      sort_order: 1,
    });
    await waitFor(() => {
      expect(texts(container)).toEqual(['Second.', 'First.']);
    });
  });

  it('edits a riddle text without touching its order', async () => {
    mocks.api.adminRiddles.mockResolvedValue([riddle('r1', 'Old wording.', 3)]);

    render(<AdminRiddles />);

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));
    const field = screen.getByLabelText('Riddle 1 text');
    fireEvent.input(field, { target: { value: 'Sharper wording.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(mocks.api.adminPatchRiddle).toHaveBeenCalledWith('ev-1', 'r1', {
        text: 'Sharper wording.',
      });
    });
  });

  it('asks before deleting and then deletes', async () => {
    mocks.api.adminRiddles.mockResolvedValue([riddle('r1', 'Doomed.', 0)]);

    render(<AdminRiddles />);

    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(mocks.api.adminDeleteRiddle).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() => {
      expect(mocks.api.adminDeleteRiddle).toHaveBeenCalledWith('ev-1', 'r1');
    });
  });

  it('shows the reason a referenced riddle cannot be deleted', async () => {
    mocks.api.adminRiddles.mockResolvedValue([riddle('r1', 'Referenced.', 0)]);
    mocks.api.adminDeleteRiddle.mockResolvedValue({
      error: 'riddle_in_use',
      message: 'Submissions reference this riddle; edit it instead.',
      status: 409,
    });

    render(<AdminRiddles />);

    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    expect(
      await screen.findByText('Submissions reference this riddle; edit it instead.'),
    ).toBeTruthy();
    expect(screen.getByText('Referenced.')).toBeTruthy();
  });

  it('refetches after a reorder that fails halfway', async () => {
    const [first, second] = [
      riddle('r1', 'First.', 0),
      riddle('r2', 'Second.', 1),
    ];
    mocks.api.adminRiddles.mockResolvedValue([first, second]);
    // The first PATCH lands, the second is refused: the server now holds
    // Second. first, so the screen must not keep showing the old order.
    mocks.api.adminPatchRiddle
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({
        error: 'riddle_not_found',
        message: 'No such riddle on this event.',
        status: 404,
      });
    mocks.api.adminRiddles
      .mockResolvedValueOnce([first, second])
      .mockResolvedValue([{ ...second, sort_order: 0 }, { ...first, sort_order: 1 }]);

    const { container } = render(<AdminRiddles />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Move riddle 2 up' }),
    );

    expect(await screen.findByText('No such riddle on this event.')).toBeTruthy();
    await waitFor(() => {
      expect(texts(container)).toEqual(['Second.', 'First.']);
    });
  });

  it('shows why the event list failed instead of asking for a new event', async () => {
    mocks.api.adminEvents.mockResolvedValue({
      error: 'internal_error',
      message: 'Something went wrong loading events.',
      status: 500,
    });

    render(<AdminRiddles />);

    expect(
      await screen.findByText('Something went wrong loading events.'),
    ).toBeTruthy();
    expect(
      screen.queryByText(
        'Create an event on the Events tab first; riddles belong to an event.',
      ),
    ).toBeNull();
  });

  it('clears a failed load when another event loads', async () => {
    mocks.api.adminEvents.mockResolvedValue([
      event,
      { id: 'ev-2', name: 'Second Night', status: 'lobby' },
    ]);
    mocks.api.adminRiddles.mockImplementation((id) =>
      id === 'ev-1'
        ? Promise.resolve({
            error: 'internal_error',
            message: 'Could not load riddles.',
            status: 500,
          })
        : Promise.resolve([riddle('r9', 'Second event riddle.', 0)]),
    );

    render(<AdminRiddles />);

    expect(await screen.findByText('Could not load riddles.')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Event'), {
      target: { value: 'ev-2' },
    });

    expect(await screen.findByText('Second event riddle.')).toBeTruthy();
    expect(screen.queryByText('Could not load riddles.')).toBeNull();
  });

  it('points at the Events tab when there is no event yet', async () => {
    mocks.api.adminEvents.mockResolvedValue([]);

    render(<AdminRiddles />);

    expect(
      await screen.findByText(
        'Create an event on the Events tab first; riddles belong to an event.',
      ),
    ).toBeTruthy();
    expect(mocks.api.adminRiddles).not.toHaveBeenCalled();
  });
});
