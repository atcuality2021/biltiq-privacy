// Tests for myModule — jest / vitest scaffold (JavaScript).
// Each test asserts ONE thing and ties to a spec acceptance criterion.
// Replace myService and placeholder values with real names.

import { describe, it, expect, vi, beforeEach } from "vitest"; // or from "@jest/globals"
import { myService } from "./myModule.js";

describe("myService.doSomething", () => {
  beforeEach(() => {
    myService.reset();
  });

  it("returns expected value for valid input", () => {
    expect(myService.doSomething("valid_input")).toBe("expected_output");
  });

  it("throws for null input", () => {
    expect(() => myService.doSomething(null)).toThrow(TypeError);
  });

  it("calls downstream function with correct argument", () => {
    const spy = vi.spyOn(myService, "_transform");
    myService.doSomething("raw");
    expect(spy).toHaveBeenCalledWith("raw");
  });
});
