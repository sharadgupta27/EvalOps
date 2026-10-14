import {
  compareVerdict,
  filterCases,
  highlightNewWords,
  sortCases,
  type CompareCase,
} from "./compare";

function c(
  id: number,
  bucket: CompareCase["bucket"],
  delta: number | null,
  output = "x",
): CompareCase {
  return {
    test_case_id: id,
    inputs: { question: `question ${id}` },
    expected_output: null,
    base_output: "base",
    head_output: output,
    base_passed: true,
    head_passed: bucket !== "regressed",
    base_score: 1,
    head_score: delta === null ? null : 1 + delta,
    delta,
    bucket,
  };
}

const CASES = [
  c(1, "unchanged", 0),
  c(2, "regressed", -0.5),
  c(3, "improved", 0.5),
  c(4, "regressed", -1, "refund denied"),
  c(5, "added", null),
];

describe("filterCases", () => {
  it("'changed' hides unchanged cases", () => {
    expect(filterCases(CASES, "changed").map((x) => x.test_case_id)).toEqual([2, 3, 4, 5]);
  });

  it("filters by bucket", () => {
    expect(filterCases(CASES, "regressed").map((x) => x.test_case_id)).toEqual([2, 4]);
    expect(filterCases(CASES, "all")).toHaveLength(5);
  });

  it("searches inputs and outputs case-insensitively", () => {
    expect(filterCases(CASES, "all", "REFUND").map((x) => x.test_case_id)).toEqual([4]);
    expect(filterCases(CASES, "all", "question 3").map((x) => x.test_case_id)).toEqual([3]);
  });
});

describe("sortCases", () => {
  it("puts the worst regressions first and does not mutate input", () => {
    const sorted = sortCases(CASES);
    expect(sorted.map((x) => x.test_case_id)).toEqual([4, 2, 3, 5, 1]);
    expect(CASES[0]?.test_case_id).toBe(1);
  });
});

describe("compareVerdict", () => {
  const counts = { regressed: 0, improved: 0, unchanged: 3, added: 0, removed: 0 };

  it("flags regressions", () => {
    expect(compareVerdict({ ...counts, regressed: 2 }, -0.2)).toEqual({
      tone: "bad",
      text: "2 cases regressed",
    });
    expect(compareVerdict({ ...counts, regressed: 1 }, 0).text).toBe("1 case regressed");
  });

  it("reports improvements and no-ops", () => {
    expect(compareVerdict({ ...counts, improved: 2 }, 0.1).tone).toBe("good");
    expect(compareVerdict(counts, 0).tone).toBe("neutral");
  });
});

describe("highlightNewWords", () => {
  it("marks words in head that are not in base", () => {
    const parts = highlightNewWords("thanks for asking", "Thanks for waiting");
    expect(parts.filter((p) => p.added).map((p) => p.text)).toEqual(["waiting"]);
    expect(parts.map((p) => p.text).join("")).toBe("Thanks for waiting");
  });
});
