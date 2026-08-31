export interface ShowcaseSlide {
  id: string;
  category: string;
  categoryLabel: string;
  accent: string; // CSS var name, e.g. "--accent-math"
  title: string;
  description: string;
  tryPrompt: string;
  mockup: "array" | "tree-graph" | "function-plot" | "neural-net" | "field" | "atom";
}

export const SHOWCASE_SLIDES: ShowcaseSlide[] = [
  {
    id: "arrays",
    category: "ARRAYS & POINTERS",
    categoryLabel: "Arrays & Pointers",
    accent: "--accent-cs",
    title: "See the Algorithm.",
    description: "Watch exactly how any algorithm runs through its data. Pointers, swaps, and all.",
    tryPrompt: "Show merge sort step by step",
    mockup: "array",
  },
  {
    id: "trees-graphs",
    category: "DATA STRUCTURES",
    categoryLabel: "Data Structures",
    accent: "--accent-cs",
    title: "Structure, Traversed.",
    description: "Trees, graphs, and everything that connects. Nodes light up as your algorithm visits them.",
    tryPrompt: "Show a graph BFS from node A",
    mockup: "tree-graph",
  },
  {
    id: "math",
    category: "MATHEMATICS",
    categoryLabel: "Mathematics",
    accent: "--accent-math",
    title: "Math Made Tangible.",
    description: "Type any function and see it come alive. Integrals, tangent lines, areas under curves.",
    tryPrompt: "Plot sin(x)·e^(-x/4) and shade the integral",
    mockup: "function-plot",
  },
  {
    id: "ai-ml",
    category: "AI & ML",
    categoryLabel: "AI & ML",
    accent: "--accent-ai",
    title: "Open the Box.",
    description: "From forward passes to attention heads, make neural networks legible to any audience.",
    tryPrompt: "Show how a CNN processes an image",
    mockup: "neural-net",
  },
  {
    id: "physics",
    category: "PHYSICS",
    categoryLabel: "Physics",
    accent: "--accent-physics",
    title: "See the Invisible.",
    description: "Field lines, wave patterns, pendulums gone chaotic. Physics made instantly intuitive.",
    tryPrompt: "Animate a double pendulum going chaotic",
    mockup: "field",
  },
  {
    id: "chemistry",
    category: "CHEMISTRY",
    categoryLabel: "Chemistry",
    accent: "--accent-chemistry",
    title: "Atoms Up Close.",
    description: "From combustion to electron orbitals, any reaction animated from a single description.",
    tryPrompt: "Show the Bohr model of carbon",
    mockup: "atom",
  },
];
