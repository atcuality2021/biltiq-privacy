// Tests for myModule — jest / vitest scaffold.
// Each test asserts ONE thing and ties to a spec acceptance criterion.
// Replace MyService and placeholder values with real names.

import { describe, it, expect, vi, beforeEach } from "vitest"; // or from "@jest/globals"
import { MyService } from "./myModule";

describe("MyService.doSomething", () => {
  let svc: MyService;

  beforeEach(() => {
    svc = new MyService();
  });

  it("returns expected value for valid input", () => {
    expect(svc.doSomething("valid_input")).toBe("expected_output");
  });

  it("throws for empty input", () => {
    expect(() => svc.doSomething("")).toThrow("input must not be empty");
  });

  it("resolves asynchronously for async variant", async () => {
    await expect(svc.doSomethingAsync("input")).resolves.toBe("async_output");
  });

  it("calls dependency with transformed argument", () => {
    const mockDep = { fetch: vi.fn().mockReturnValue("mocked") };
    const svcWithDep = new MyService(mockDep);
    svcWithDep.doSomething("input");
    expect(mockDep.fetch).toHaveBeenCalledWith("transformed_input");
  });
});
