/** Small static SVG illustrations standing in for a real rendered preview
 * per category — deliberately simple line-art, not attempting to fake an
 * actual video frame, so it never looks like a broken video player. */
export function ShowcaseMockup({ kind }: { kind: string }) {
  switch (kind) {
    case "array":
      return <ArrayMockup />;
    case "tree-graph":
      return <TreeGraphMockup />;
    case "function-plot":
      return <FunctionPlotMockup />;
    case "neural-net":
      return <NeuralNetMockup />;
    case "field":
      return <FieldMockup />;
    case "atom":
      return <AtomMockup />;
    default:
      return null;
  }
}

function ArrayMockup() {
  const values = [5, 2, 8, 1, 9, 3];
  return (
    <svg viewBox="0 0 360 140" className="mockup-svg">
      {values.map((v, i) => (
        <g key={i} transform={`translate(${20 + i * 56}, 30)`}>
          <rect
            width="46"
            height="46"
            rx="8"
            fill={i === 1 || i === 4 ? "var(--mockup-accent)" : "#1b2230"}
            stroke="#3d4a5c"
            opacity={i === 1 || i === 4 ? 0.9 : 1}
          />
          <text x="23" y="30" textAnchor="middle" fontSize="18" fill="#f5f7fa" fontFamily="var(--font-mono)">
            {v}
          </text>
        </g>
      ))}
      <path d="M 46 90 L 46 100" stroke="var(--mockup-accent)" strokeWidth="2" markerEnd="url(#arrow)" />
      <path d="M 270 90 L 270 100" stroke="var(--mockup-accent)" strokeWidth="2" markerEnd="url(#arrow)" />
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="var(--mockup-accent)" />
        </marker>
      </defs>
    </svg>
  );
}

function TreeGraphMockup() {
  return (
    <svg viewBox="0 0 360 160" className="mockup-svg">
      <g stroke="#3d4a5c" strokeWidth="2" fill="none">
        <path d="M180 30 L100 80" />
        <path d="M180 30 L260 80" />
        <path d="M100 80 L60 130" />
        <path d="M100 80 L140 130" />
        <path d="M260 80 L300 130" stroke="var(--mockup-accent)" />
      </g>
      {[
        [180, 30, "8"],
        [100, 80, "3"],
        [260, 80, "10"],
        [60, 130, "1"],
        [140, 130, "6"],
        [300, 130, "14"],
      ].map(([cx, cy, label], i) => (
        <g key={i}>
          <circle cx={cx as number} cy={cy as number} r="18" fill={i === 2 || i === 5 ? "var(--mockup-accent)" : "#1b2230"} stroke="#3d4a5c" />
          <text x={cx as number} y={(cy as number) + 5} textAnchor="middle" fontSize="13" fill="#f5f7fa" fontFamily="var(--font-mono)">
            {label}
          </text>
        </g>
      ))}
    </svg>
  );
}

function FunctionPlotMockup() {
  return (
    <svg viewBox="0 0 360 160" className="mockup-svg">
      <path d="M20 140 L340 140" stroke="#3d4a5c" strokeWidth="1.5" />
      <path d="M20 140 L20 20" stroke="#3d4a5c" strokeWidth="1.5" />
      <path
        d="M30 138 C 70 40, 110 30, 150 90 S 230 150, 270 100 S 320 60, 340 70"
        stroke="var(--mockup-accent)"
        strokeWidth="3"
        fill="none"
      />
      <path
        d="M30 138 C 70 40, 110 30, 150 90 L150 140 Z"
        fill="var(--mockup-accent)"
        opacity="0.18"
      />
      <circle cx="150" cy="90" r="5" fill="var(--mockup-accent)" />
    </svg>
  );
}

function NeuralNetMockup() {
  const layers = [2, 3, 3, 2];
  const xs = [40, 140, 240, 320];
  const positions = layers.map((n, li) =>
    Array.from({ length: n }, (_, i) => ({
      x: xs[li],
      y: 30 + (i + 1) * (140 / (n + 1)),
    }))
  );
  return (
    <svg viewBox="0 0 360 160" className="mockup-svg">
      {positions.slice(0, -1).map((layer, li) =>
        layer.map((p, pi) =>
          positions[li + 1].map((q, qi) => (
            <line
              key={`${li}-${pi}-${qi}`}
              x1={p.x}
              y1={p.y}
              x2={q.x}
              y2={q.y}
              stroke="#262d3a"
              strokeWidth="1"
            />
          ))
        )
      )}
      {positions.map((layer, li) =>
        layer.map((p, pi) => (
          <circle
            key={`${li}-${pi}`}
            cx={p.x}
            cy={p.y}
            r="9"
            fill={li === 2 && pi === 1 ? "var(--mockup-accent)" : "none"}
            stroke={li === 2 && pi === 1 ? "var(--mockup-accent)" : "#5c6672"}
            strokeWidth="2"
          />
        ))
      )}
    </svg>
  );
}

function FieldMockup() {
  const rows = 6;
  const cols = 10;
  const cellW = 34;
  const cellH = 22;
  const arrows = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cx = 20 + c * cellW;
      const cy = 15 + r * cellH;
      const dx = cx - 180;
      const dy = cy - 80;
      const len = Math.max(Math.hypot(dx, dy), 1);
      const ux = (dx / len) * 8;
      const uy = (dy / len) * 8;
      arrows.push(
        <line
          key={`${r}-${c}`}
          x1={cx - ux}
          y1={cy - uy}
          x2={cx + ux}
          y2={cy + uy}
          stroke="var(--mockup-accent)"
          strokeWidth="1.5"
          opacity="0.7"
          markerEnd="url(#field-arrow)"
        />
      );
    }
  }
  return (
    <svg viewBox="0 0 360 160" className="mockup-svg">
      <defs>
        <marker id="field-arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill="var(--mockup-accent)" />
        </marker>
      </defs>
      {arrows}
      <circle cx="180" cy="80" r="10" fill="var(--mockup-accent)" />
    </svg>
  );
}

function AtomMockup() {
  // Three electron "shells" as ellipses rotated 60° apart (a simple Bohr-
  // style stand-in, not a physically accurate orbital diagram). Electron
  // dots are placed by actually walking each ellipse's own parametric
  // form and rotation, rather than reusing the first ellipse's geometry
  // for all three, which is what put the dots near the nucleus instead
  // of on the rings.
  const ellipses = [
    { rx: 150, ry: 55, rotation: 0 },
    { rx: 55, ry: 150, rotation: 60 },
    { rx: 55, ry: 150, rotation: -60 },
  ];
  const cx = 180;
  const cy = 80;

  function pointOnEllipse(rx: number, ry: number, rotationDeg: number, paramDeg: number) {
    const paramRad = (paramDeg * Math.PI) / 180;
    const ex = rx * Math.cos(paramRad);
    const ey = ry * Math.sin(paramRad);
    const rotRad = (rotationDeg * Math.PI) / 180;
    const x = ex * Math.cos(rotRad) - ey * Math.sin(rotRad);
    const y = ex * Math.sin(rotRad) + ey * Math.cos(rotRad);
    return { x: cx + x, y: cy + y };
  }

  return (
    <svg viewBox="0 0 360 160" className="mockup-svg">
      {ellipses.map((e, i) => (
        <ellipse
          key={i}
          cx={cx}
          cy={cy}
          rx={e.rx}
          ry={e.ry}
          fill="none"
          stroke="#3d4a5c"
          strokeWidth="1.5"
          transform={e.rotation ? `rotate(${e.rotation} ${cx} ${cy})` : undefined}
        />
      ))}
      <circle cx={cx} cy={cy} r="12" fill="var(--mockup-accent)" />
      {ellipses.map((e, i) => {
        const p = pointOnEllipse(e.rx, e.ry, e.rotation, 35);
        return <circle key={i} cx={p.x} cy={p.y} r="6" fill="#334155" stroke="#0f172a" strokeWidth="1" />;
      })}
    </svg>
  );
}
