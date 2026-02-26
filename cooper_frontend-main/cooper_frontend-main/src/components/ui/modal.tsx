import React from 'react';
import ReactDOM from 'react-dom';

interface ModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Close handler – triggered on backdrop click or close button */
  onClose: () => void;
  /** Optional heading text */
  title?: string;
  /** Modal body */
  children: React.ReactNode;
}

/**
 * Basic Modal component.
 * Renders its children inside a centred card with a dimmed backdrop.
 * Uses a React portal so that it is rendered at the document root level.
 */
const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '12px',
          width: '90%',
          maxWidth: '720px',
          maxHeight: '90vh',
          overflowY: 'auto',
          padding: '1.5rem',
          boxShadow: '0 4px 15px rgba(0, 0, 0, 0.2)',
          position: 'relative'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          {title && <h2 style={{ margin: 0 }}>{title}</h2>}
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: '1.5rem',
              cursor: 'pointer',
              lineHeight: 1
            }}
            aria-label="Close"
          >
            &times;
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  );
};

export default Modal; 