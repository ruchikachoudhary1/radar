import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

/**
 * Transient notifications.
 *
 * Replaces the inline banners for things that happened rather than things that
 * are true: "added to your tracker", "couldn't reach that board". A banner that
 * pushes the page down every time you click something is worse than one that
 * appears in the corner and leaves.
 *
 * Errors stay until dismissed. Successes leave on their own — you already know
 * it worked, and a message you have to clear is a small tax on every action.
 */
const ToastContext = createContext(() => {});

export function useToast() {
  return useContext(ToastContext);
}

let nextId = 1;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((message, tone = "info") => {
    if (!message) return;
    const id = nextId++;
    setToasts((list) => [...list, { id, message, tone }]);
    return id;
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      {/* Announced politely so a screen reader hears the outcome without
          losing the user's place in the page. */}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <Toast key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function Toast({ toast, onDismiss }) {
  useEffect(() => {
    // Errors are worth reading twice, so only the others expire.
    if (toast.tone === "error") return undefined;
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [toast.tone, onDismiss]);

  return (
    <div className={`toast toast-${toast.tone}`}>
      <span>{toast.message}</span>
      <button className="toast-x" onClick={onDismiss} aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}
