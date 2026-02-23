/**
 * Validation utility for DCF scenario analysis
 * Ensures scenarios follow logical ordering (Bull >= Base >= Bear)
 */

export type Scenario = {
  label: 'Bull' | 'Base' | 'Bear';
  probability: number;
  value: number;
};

export type ValidationResult = {
  ok: boolean;
  errors: string[];
  suggestions?: Scenario[];
};

/**
 * Validates DCF scenarios and detects logical inconsistencies
 * 
 * Validation checks:
 * 1. Probabilities exist and sum to ~100% (±0.5% tolerance)
 * 2. Values are positive numbers
 * 3. Logical ordering: Bull >= Base >= Bear
 * 
 * @param scenarios - Array of scenario objects
 * @returns ValidationResult with ok status, errors, and optional suggestions
 */
export function validateScenarios(scenarios: Scenario[]): ValidationResult {
  const errors: string[] = [];
  
  // Check 1: Probabilities sum to 100%
  const probSum = scenarios.reduce((sum, s) => sum + (Number(s.probability) || 0), 0);
  if (Math.abs(probSum - 100) > 0.5) {
    errors.push(`Probabilities must sum to 100% (got ${probSum.toFixed(1)}%)`);
  }
  
  // Check 2: All values are positive numbers
  const invalidValues = scenarios.filter(s => !isFinite(s.value) || s.value <= 0);
  if (invalidValues.length > 0) {
    errors.push('All scenario values must be positive numbers');
  }
  
  // Check 3: All required labels present
  const labels = scenarios.map(s => s.label.toLowerCase());
  const requiredLabels = ['bull', 'base', 'bear'];
  const missingLabels = requiredLabels.filter(label => !labels.includes(label));
  if (missingLabels.length > 0) {
    errors.push(`Missing scenarios: ${missingLabels.join(', ').toUpperCase()}`);
  }
  
  // Check 4: Logical ordering (Bull >= Base >= Bear)
  const byLabel = Object.fromEntries(
    scenarios.map(s => [s.label.toLowerCase(), s])
  );
  const bull = byLabel['bull']?.value ?? null;
  const base = byLabel['base']?.value ?? null;
  const bear = byLabel['bear']?.value ?? null;
  
  const okOrder = bull !== null && base !== null && bear !== null 
    && (bull >= base && base >= bear);
  
  if (!okOrder && bull !== null && base !== null && bear !== null) {
    errors.push('Scenarios are logically inverted: Bull should be highest, Bear lowest');
  }
  
  // Generate safe suggestion if ordering is wrong
  const suggestions = !okOrder && bull !== null && base !== null && bear !== null
    ? (() => {
        // Create a copy to sort without mutating original
        const sorted = [...scenarios].sort((a, b) => b.value - a.value);
        
        // Map sorted values to labels, preserving original probabilities
        const probMap = Object.fromEntries(
          scenarios.map(s => [s.label.toLowerCase(), s.probability])
        );
        
        return [
          {
            label: 'Bull' as const,
            probability: probMap['bull'] ?? 25,
            value: sorted[0].value
          },
          {
            label: 'Base' as const,
            probability: probMap['base'] ?? 50,
            value: sorted[1].value
          },
          {
            label: 'Bear' as const,
            probability: probMap['bear'] ?? 25,
            value: sorted[2].value
          }
        ];
      })()
    : undefined;
  
  return {
    ok: errors.length === 0 && okOrder,
    errors,
    suggestions
  };
}

/**
 * Formats currency for display
 */
export function formatCurrency(value: number, currency: 'INR' | 'USD' = 'INR'): string {
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
    minimumFractionDigits: 2
  }).format(value);
  
  return formatted;
}

/**
 * Log telemetry events for DCF scenario issues
 */
export function logScenarioEvent(
  event: 'dcf_scenario_inconsistent' | 'dcf_scenario_autofix' | 'dcf_scenario_user_cancel',
  data: Record<string, any>
): void {
  // In production, send to analytics service
  console.log(`[Telemetry] ${event}`, data);
  
  // Example: Send to analytics endpoint
  if (typeof window !== 'undefined' && (window as any).gtag) {
    (window as any).gtag('event', event, data);
  }
}

