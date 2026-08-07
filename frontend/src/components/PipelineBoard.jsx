import React, { useRef, useState } from "react";

/**
 * The pipeline as a board you can drag cards across.
 *
 * Dragging is the fast path, not the only one: each card keeps a stage menu,
 * because drag-and-drop is awkward with a keyboard, unusable on a phone, and
 * fiddly for anyone with a tremor. The board is a nicer way to do the same
 * thing, never the required way.
 */
export default function PipelineBoard({ items, statuses, onMove, onView, onReplied }) {
  // What is being dragged is kept in a ref as well as in state. State drives
  // the dimming, but a ref is what the drop handler reads: state would only be
  // correct if React happened to re-render between dragstart and drop, which
  // is true in practice and not something to depend on.
  const held = useRef(null);
  const [dragging, setDragging] = useState(null);
  const [over, setOver] = useState(null);

  function startDrag(app, event) {
    held.current = app;
    setDragging(app);
    // Also stated the HTML5 way, so the drag is well-formed for the browser
    // and works if the ref is ever lost to a remount.
    event.dataTransfer?.setData("text/plain", String(app.id));
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
  }

  function endDrag() {
    held.current = null;
    setDragging(null);
    setOver(null);
  }

  function drop(status, event) {
    const app =
      held.current ||
      items.find((it) => String(it.id) === event.dataTransfer?.getData("text/plain"));
    if (app && app.status !== status) onMove(app.id, status);
    endDrag();
  }

  return (
    <div className="board">
      {statuses.map((status) => {
        const column = items.filter((it) => it.status === status);
        return (
          <div
            key={status}
            className={`board-col ${over === status ? "over" : ""}`}
            onDragOver={(e) => {
              // Preventing the default is what marks this a valid drop target.
              e.preventDefault();
              if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
              setOver(status);
            }}
            onDragLeave={() => setOver((s) => (s === status ? null : s))}
            onDrop={(e) => {
              e.preventDefault();
              drop(status, e);
            }}
          >
            <div className="board-head">
              <span>{status}</span>
              <span className="board-count">{column.length}</span>
            </div>

            <div className="board-body">
              {column.length === 0 && <div className="board-empty">Nothing here</div>}

              {column.map((app) => {
                const urg = app.urgency || { level: "neutral", label: "" };
                return (
                  <div
                    key={app.id}
                    className={`board-card edge edge-${urg.level} ${
                      dragging?.id === app.id ? "lifting" : ""
                    }`}
                    draggable
                    onDragStart={(e) => startDrag(app, e)}
                    onDragEnd={endDrag}
                  >
                    <div className="board-title">{app.title || "Untitled role"}</div>
                    <div className="muted" style={{ fontSize: 12.5 }}>
                      {app.company || "Unknown company"}
                    </div>

                    {urg.label && (
                      <span
                        className={`urg urg-${urg.level}`}
                        style={{ marginTop: 9, display: "inline-block" }}
                      >
                        {urg.label}
                      </span>
                    )}

                    <div className="board-actions">
                      <select
                        value={app.status}
                        onChange={(e) => onMove(app.id, e.target.value)}
                        aria-label={`Stage for ${app.title || "this application"}`}
                      >
                        {statuses.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                      <button className="link-btn" onClick={() => onView(app.id)}>
                        Open
                      </button>
                      {!app.replied && !["Rejected", "Offer", "Saved"].includes(app.status) && (
                        <button className="link-btn" onClick={() => onReplied(app.id)}>
                          Replied
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
