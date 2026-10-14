import {
  formatCost,
  formatDeltaPoints,
  formatLatency,
  formatPercent,
  formatScore,
  formatTokens,
  previewInputs,
  progressPercent,
  scoreTone,
} from "./format";

describe("format", () => {
  it("formats percentages and missing values", () => {
    expect(formatPercent(0.833)).toBe("83%");
    expect(formatPercent(0.8333, 1)).toBe("83.3%");
    expect(formatPercent(null)).toBe("n/a");
    expect(formatPercent(Number.NaN)).toBe("n/a");
  });

  it("formats signed percentage-point deltas", () => {
    expect(formatDeltaPoints(0.125)).toBe("+12.5 pp");
    expect(formatDeltaPoints(-0.4)).toBe("−40.0 pp");
    expect(formatDeltaPoints(0.0001)).toBe("±0 pp");
    expect(formatDeltaPoints(null)).toBe("n/a");
  });

  it("formats scores, cost, latency and tokens", () => {
    expect(formatScore(0.75)).toBe("0.75");
    expect(formatCost(0)).toBe("$0");
    expect(formatCost(0.00042)).toBe("$0.0004");
    expect(formatCost(1.234)).toBe("$1.23");
    expect(formatLatency(450.4)).toBe("450 ms");
    expect(formatLatency(2300)).toBe("2.3 s");
    expect(formatTokens(950)).toBe("950");
    expect(formatTokens(12_400)).toBe("12.4k");
    expect(formatTokens(3_200_000)).toBe("3.2M");
  });

  it("maps scores to tones", () => {
    expect(scoreTone(0.95)).toBe("good");
    expect(scoreTone(0.6)).toBe("warn");
    expect(scoreTone(0.2)).toBe("bad");
    expect(scoreTone(undefined)).toBe("none");
  });

  it("computes bounded progress", () => {
    expect(progressPercent(3, 4)).toBe(75);
    expect(progressPercent(5, 4)).toBe(100);
    expect(progressPercent(0, 0)).toBe(0);
  });

  it("previews inputs and truncates", () => {
    expect(previewInputs({ q: "hi", n: 2 })).toBe("q: hi, n: 2");
    const long = previewInputs({ q: "x".repeat(200) }, 20);
    expect(long).toHaveLength(20);
    expect(long.endsWith("…")).toBe(true);
  });
});
