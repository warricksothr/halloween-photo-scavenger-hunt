import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: { modSetNickname: vi.fn() },
}));

vi.mock('../../api', () => ({ api: mocks.api }));

import { NicknameForm } from './NicknameForm';

// The nickname players see on a moderator's verdicts (ADR 0045).
describe('moderator nickname form', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('says players see no name until one is set', () => {
    render(<NicknameForm nickname={null} />);
    expect(screen.getByText('Players see no name for you')).toBeTruthy();
  });

  it('shows the current nickname', () => {
    render(<NicknameForm nickname="Oracle" />);
    expect(screen.getByText('Oracle')).toBeTruthy();
    expect(screen.getByLabelText(/^Nickname/).value).toBe('Oracle');
    // Nothing changed yet, so there is nothing to save.
    expect(screen.getByRole('button', { name: 'Save nickname' }).disabled).toBe(true);
  });

  it('saves the trimmed nickname and tells the shell', async () => {
    mocks.api.modSetNickname.mockResolvedValue({ nickname: 'Oracle' });
    const onSaved = vi.fn();
    render(<NicknameForm nickname={null} onSaved={onSaved} />);

    fireEvent.input(screen.getByLabelText(/^Nickname/), { target: { value: '  Oracle ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save nickname' }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith('Oracle'));
    expect(mocks.api.modSetNickname).toHaveBeenCalledWith('Oracle');
    expect(screen.getByRole('status').textContent).toBe('Saved.');
  });

  it('clears the nickname with an empty field', async () => {
    mocks.api.modSetNickname.mockResolvedValue({ nickname: null });
    const onSaved = vi.fn();
    render(<NicknameForm nickname="Oracle" onSaved={onSaved} />);

    fireEvent.input(screen.getByLabelText(/^Nickname/), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save nickname' }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(null));
    expect(mocks.api.modSetNickname).toHaveBeenCalledWith('');
  });

  it('shows the server refusal and keeps the draft', async () => {
    mocks.api.modSetNickname.mockResolvedValue({ error: 'validation', message: 'Too long.' });
    const onSaved = vi.fn();
    render(<NicknameForm nickname={null} onSaved={onSaved} />);

    fireEvent.input(screen.getByLabelText(/^Nickname/), { target: { value: 'Oracle' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save nickname' }));

    expect((await screen.findByRole('alert')).textContent).toBe('Too long.');
    expect(onSaved).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/^Nickname/).value).toBe('Oracle');
  });
});
