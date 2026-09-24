// The full-size photo view: a fixed overlay over the whole console, so a
// small detail (a four-digit house number) can be read. Escape, the
// backdrop, or the close button dismisses it.
import { useEffect, useRef } from 'preact/hooks';

export function Lightbox({ photo, onClose }) {
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      class="mod-lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={photo.label}
      onClick={(event) => {
        // The backdrop closes it; a click on the photo itself does not.
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <img src={photo.src} alt={photo.label} />
      <button ref={closeRef} type="button" class="btn secondary mod-lightbox-close" onClick={onClose}>
        Close
      </button>
    </div>
  );
}
