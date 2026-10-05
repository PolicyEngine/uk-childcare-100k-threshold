import { describe, expect, it } from "vitest";

import { colorFor, schemeColors } from "./colors";
import { SCHEMES } from "./dataHelpers";

describe("colorFor", () => {
  it("returns the assigned colour for each scheme", () => {
    for (const id of SCHEMES) expect(colorFor(id)).toBe(schemeColors[id]);
  });

  it("throws on an unknown scheme id instead of guessing", () => {
    expect(() => colorFor("mystery_scheme")).toThrow(/No colour assigned/);
  });
});
