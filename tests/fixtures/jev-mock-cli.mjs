console.log(JSON.stringify({
  verdicts: [{ id: "candidate", type: "choice", answer: "A", confidence: 0.91, confidenceFrom: "reported", escalate: false }],
  backend: "mock",
  model: "fixture",
  latencyMs: 1,
  usage: { inputTokens: 1, outputTokens: 1 }
}));
