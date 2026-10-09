import { describe, expect, it } from "vitest";

import { describeApiDetail } from "./api-errors";

describe("describeApiDetail", () => {
  it("returns a plain string unchanged", () => {
    expect(describeApiDetail("Superadmin access required", "fallback")).toBe("Superadmin access required");
  });

  it("flattens FastAPI validation errors with their field and without the body prefix", () => {
    const detail = [
      { loc: ["body", "key"], msg: "String should match pattern" },
      { loc: ["body", "monthly_price_cents"], msg: "Input should be greater than or equal to 0" },
    ];
    expect(describeApiDetail(detail, "fallback")).toBe("key: String should match pattern; monthly_price_cents: Input should be greater than or equal to 0");
  });

  it("keeps a message that has no location", () => {
    expect(describeApiDetail([{ msg: "Value error" }, "plain"], "fallback")).toBe("Value error; plain");
  });

  it("never prints [object Object]: unknown shapes fall back", () => {
    for (const detail of [{ a: 1 }, null, undefined, 42, [], [{}], ""]) {
      expect(describeApiDetail(detail, "fallback")).toBe("fallback");
    }
  });
});
