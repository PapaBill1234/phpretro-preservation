import { ArrowLeft, Check } from 'lucide-react';
import type { ReactNode } from 'react';

// Shared by the original Codex wizard and its OpenHands runtime adapter.
export function OptimizationHeader({ title, subtitle, backLabel, onBack }: {
  title: string; subtitle: string; backLabel: string; onBack: () => void;
}) {
  return <header className="opt-heading"><div><h1>{title}</h1><p>{subtitle}</p></div>
    <button className="button ghost" onClick={onBack}><ArrowLeft size={16} />{backLabel}</button>
  </header>;
}

export function OptimizationSteps({ step, sessionPresent, labels, details, onStep }: {
  step: number; sessionPresent: boolean; labels: string[]; details?: string[]; onStep: (step: number) => void;
}) {
  return <nav className="opt-steps" aria-label="Optimization steps">
    {labels.map((label, index) => <button key={label} className={`opt-step ${step === index + 1 ? 'active' : ''}`}
      aria-current={step === index + 1 ? 'step' : undefined} onClick={() => onStep(index + 1)}>
      <span className="opt-step-number">{index === 0 && sessionPresent ? <Check size={18} /> : index + 1}</span>
      <span><strong>{label}</strong>{details?.[index] && <small>{details[index]}</small>}</span>
    </button>)}
  </nav>;
}

export function OptimizationSessionBar({ children }: { children: ReactNode }) {
  return <div className="opt-session-bar">{children}</div>;
}
