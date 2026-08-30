import "./EmptyState.css";

export function EmptyState() {
  return (
    <div className="empty-state">
      <p className="empty-state__glyph">▸</p>
      <p className="empty-state__text">
        Describe an algorithm above, or pick one from your history to see it here.
      </p>
    </div>
  );
}
