/** Human-readable labels only; identifiers and exported records stay unchanged. */
export function displayLabel(value: string): string {
  const labels: Record<string, string> = {
    preserve: "Preserved context",
    compact: "Compacted context",
    reference: "Reference policy",
    model: "Model",
    pass: "Passed",
    fail: "Failed",
    "late-order-exception": "Prior compensation exception",
    "late-order-standard": "Standard late order",
    "insufficient-evidence": "Missing evidence",
    "null-calibration": "Null calibration",
    "planted-regression": "Planted regression",
    "reference-repair": "Reference repair",
  };
  const key = value.toLowerCase();
  if (Object.hasOwn(labels, key)) return labels[key];
  const text = value.replace(/[_-]+/g, " ").toLowerCase();
  return (text.charAt(0).toUpperCase() + text.slice(1)).replace(
    /\b(json|api|oidc|llm|http|sql|sha)\b/gi,
    (word) => word.toUpperCase(),
  );
}

/** Sentence case for explanatory copy; raw evidence is rendered separately. */
export function sentenceText(value: string): string {
  const text = value.trim();
  if (!text) return text;
  const sentence = text.charAt(0).toUpperCase() + text.slice(1);
  return /[.!?]$/.test(sentence) ? sentence : sentence + ".";
}
