import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { describe, expect, it, vi } from 'vitest';

import { ScanQr } from './ScanQr';

const copy = {
  screens: {
    join: {
      scan: {
        button: 'Scan QR code',
        reading: 'Reading…',
        hint: 'Take a photo.',
        notFound: 'NO_CODE',
        notOurs: 'NOT_OURS',
      },
    },
  },
};

function pick(file = new File(['x'], 'qr.jpg', { type: 'image/jpeg' })) {
  fireEvent.change(screen.getByLabelText('Scan QR code'), { target: { files: [file] } });
}

describe('Scan QR code (ADR 0043)', () => {
  it('opens the camera for a still photo, not a live view', () => {
    render(<ScanQr copy={copy} decode={vi.fn()} navigate={vi.fn()} />);
    const input = screen.getByLabelText('Scan QR code');
    expect(input.getAttribute('type')).toBe('file');
    expect(input.getAttribute('accept')).toBe('image/*');
    expect(input.getAttribute('capture')).toBe('environment');
  });

  it('opens the hunt link the QR carries', async () => {
    const navigate = vi.fn();
    const decode = vi.fn().mockResolvedValue(`${window.location.origin}/j/ABCD234567`);
    render(<ScanQr copy={copy} decode={decode} navigate={navigate} />);
    pick();
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/j/ABCD234567'));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('refuses a QR that is not a link for this hunt', async () => {
    const navigate = vi.fn();
    const decode = vi.fn().mockResolvedValue('https://elsewhere.example/j/ABCD234567');
    render(<ScanQr copy={copy} decode={decode} navigate={navigate} />);
    pick();
    expect((await screen.findByRole('alert')).textContent).toContain('NOT_OURS');
    expect(navigate).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Scan QR code' }).disabled).toBe(false);
  });

  it('says so when the photo has no readable code, or cannot be read', async () => {
    const decode = vi.fn().mockResolvedValueOnce(null).mockRejectedValueOnce(new Error('bad image'));
    render(<ScanQr copy={copy} decode={decode} navigate={vi.fn()} />);
    pick();
    expect((await screen.findByRole('alert')).textContent).toContain('NO_CODE');
    pick();
    await waitFor(() => expect(decode).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('alert').textContent).toContain('NO_CODE');
  });
});
