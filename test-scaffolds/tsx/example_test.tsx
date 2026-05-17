// Tests for MyComponent — jest / vitest + @testing-library/react scaffold.
// tsx uses the same framework as typescript; this scaffold demonstrates React
// component testing. Replace MyComponent and placeholder values with real names.

import { describe, it, expect, vi } from "vitest"; // or from "@jest/globals"
import { render, screen, fireEvent } from "@testing-library/react";
import { MyComponent } from "./MyComponent";

describe("MyComponent", () => {
  it("renders the label prop", () => {
    render(<MyComponent label="Hello" />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("calls onSubmit when the button is clicked", () => {
    const onSubmit = vi.fn();
    render(<MyComponent label="Click me" onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: /click me/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("shows error message for invalid input", () => {
    render(<MyComponent label="Submit" />);
    fireEvent.submit(screen.getByRole("form"));
    expect(screen.getByRole("alert")).toHaveTextContent("required");
  });
});
