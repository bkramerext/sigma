/** One presentation for model names and relative API price tiers throughout SIGMA. */
export type PricedModel = { id: string; label: string; relative_cost: string };

const reviewedNames: Record<string, string> = {
  'gpt-6-luna': 'GPT-6-Luna',
  'gpt-6.1-sol': 'GPT-6.1-Sol',
  'gpt-6-astra': 'GPT-6-Astra',
};

export function modelDisplayName(model: PricedModel): string {
  return reviewedNames[model.id] ??
    model.label.replace(/\s*\(\${1,3}\)\s*$/, '').replace(/\s*·\s*\${1,3}\s*$/, '').trim();
}

export function modelDisplayLabel(model: PricedModel): string {
  const name = modelDisplayName(model);
  return /^\${1,3}$/.test(model.relative_cost) ? `${name} · ${model.relative_cost}` : name;
}
