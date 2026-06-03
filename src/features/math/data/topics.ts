export interface MathFormula {
  name: string;
  latex: string;
  note?: string;
}

export interface MathTopic {
  id: string;
  label: string;
  backendTopic: string;
  description: string;
  questionCount: number;
  formulas: MathFormula[];
  readSections: { title: string; body: string }[];
  infographicBullets: string[];
}

export const MATH_TOPICS: MathTopic[] = [
  {
    id: "arithmetic",
    label: "Arithmetic",
    backendTopic: "Arithmetic",
    description: "Even/odd drills, addition, multiplication foundations.",
    questionCount: 5,
    formulas: [
      { name: "Average", latex: "avg = sum / n" },
      { name: "Percent", latex: "part = (pct/100) × whole" },
    ],
    readSections: [
      { title: "Number types", body: "Even numbers divide by 2; odd numbers do not. Use parity to simplify mental math." },
      { title: "Order of operations", body: "PEMDAS: parentheses, exponents, multiply/divide, add/subtract." },
    ],
    infographicBullets: ["Build speed with timed drills", "Track accuracy per operation", "Reports show weak operands"],
  },
  {
    id: "algebra",
    label: "Algebra",
    backendTopic: "Algebra",
    description: "Simplify expressions, linear equations, factoring.",
    questionCount: 5,
    formulas: [
      { name: "Linear", latex: "ax + b = c  →  x = (c−b)/a" },
      { name: "Distribute", latex: "a(b + c) = ab + ac" },
      { name: "Like terms", latex: "ax + bx = (a+b)x" },
    ],
    readSections: [
      { title: "Combine like terms", body: "Only terms with the same variable power can merge coefficients." },
      { title: "Factoring", body: "Find two numbers that multiply to c and add to b for x²+bx+c." },
    ],
    infographicBullets: ["Whiteboard for scratch work", "Step-by-step explanations after submit", "Mastery saved when logged in"],
  },
  {
    id: "geometry",
    label: "Geometry",
    backendTopic: "Geometry",
    description: "Angles, triangles, circles, perimeter.",
    questionCount: 5,
    formulas: [
      { name: "Triangle angles", latex: "α + β + γ = 180°" },
      { name: "Supplementary", latex: "α + β = 180°" },
      { name: "Complementary", latex: "α + β = 90°" },
      { name: "Circle radius", latex: "r = d/2" },
    ],
    readSections: [
      { title: "Angle pairs", body: "Supplementary = straight line; complementary = right angle." },
      { title: "Triangles", body: "Interior angles always sum to 180°." },
    ],
    infographicBullets: ["Visualize on whiteboard", "GRE-style word problems", "Session report with timing"],
  },
  {
    id: "calculus",
    label: "Calculus",
    backendTopic: "Calculus",
    description: "Derivatives and power rule basics.",
    questionCount: 5,
    formulas: [
      { name: "Power rule", latex: "d/dx xⁿ = n·xⁿ⁻¹" },
      { name: "Constant", latex: "d/dx c = 0" },
      { name: "Sum rule", latex: "d/dx (f+g) = f′ + g′" },
    ],
    readSections: [
      { title: "Power rule", body: "Bring exponent down, reduce power by one." },
      { title: "Linearity", body: "Differentiate term-by-term for sums." },
    ],
    infographicBullets: ["SymPy-backed problems when API available", "Practice timer per question", "Review report at end"],
  },
  {
    id: "trigonometry",
    label: "Trigonometry",
    backendTopic: "Trigonometry",
    description: "Unit circle values and inverse trig.",
    questionCount: 5,
    formulas: [
      { name: "sin 30°", latex: "1/2" },
      { name: "cos 0°", latex: "1" },
      { name: "tan 45°", latex: "1" },
    ],
    readSections: [
      { title: "Standard angles", body: "Memorize sin/cos for 0°, 30°, 45°, 60°, 90°." },
      { title: "Inverse", body: "sin⁻¹(0.5) = 30° on [0°, 90°]." },
    ],
    infographicBullets: ["Quick recall drills", "Connect to geometry angles", "Track weak angles in report"],
  },
];

export function getMathTopic(id: string): MathTopic | undefined {
  return MATH_TOPICS.find((t) => t.id === id);
}

/** Local practice sets (reference Simplify Quiz UI) when backend has no template */
export const LOCAL_QUESTION_SETS: Record<
  string,
  { question: string; answer: string; explanation: string }[]
> = {
  geometry: [
    { question: "Two supplementary angles. One is 65°. Find the other.", answer: "115", explanation: "180° − 65° = 115°." },
    { question: "Triangle angles 45° and 60°. Third angle?", answer: "75", explanation: "180° − 45° − 60° = 75°." },
    { question: "Diameter 10cm. Radius?", answer: "5", explanation: "r = d/2." },
    { question: "Square side 7cm. Perimeter?", answer: "28", explanation: "4 × 7 = 28cm." },
    { question: "Complement of 35°?", answer: "55", explanation: "90° − 35° = 55°." },
  ],
  calculus: [
    { question: "dy/dx: y = x²", answer: "2x", explanation: "Power rule." },
    { question: "dy/dx: y = 3x³ + 2x", answer: "9x^2+2", explanation: "Apply power rule per term." },
    { question: "dy/dx: y = 5x⁴", answer: "20x^3", explanation: "4·5x³." },
    { question: "dy/dx: y = x² + 3x + 1", answer: "2x+3", explanation: "2x + 3 + 0." },
    { question: "dy/dx: y = 2x³ − x²", answer: "6x^2-2x", explanation: "6x² − 2x." },
  ],
  trigonometry: [
    { question: "sin(30°) = ?", answer: "0.5", explanation: "Standard value 1/2." },
    { question: "cos(0°) = ?", answer: "1", explanation: "Adjacent equals hypotenuse." },
    { question: "tan(45°) = ?", answer: "1", explanation: "Opposite = adjacent." },
    { question: "sin(90°) = ?", answer: "1", explanation: "Maximum sine." },
    { question: "sin(θ)=0.5, θ in [0,90]", answer: "30", explanation: "sin⁻¹(0.5)=30°." },
  ],
  algebra: [
    { question: "Simplify: 3x + 7x + 3", answer: "10x+3", explanation: "Combine like terms." },
    { question: "Simplify: 5(2x + 3)", answer: "10x+15", explanation: "Distribute." },
    { question: "Solve: 2x + 5 = 13", answer: "4", explanation: "x = 4." },
    { question: "Simplify: x² + 3x² − 2x", answer: "4x^2-2x", explanation: "4x² − 2x." },
    { question: "Factor: x² + 5x + 6", answer: "(x+2)(x+3)", explanation: "2 and 3." },
  ],
};
