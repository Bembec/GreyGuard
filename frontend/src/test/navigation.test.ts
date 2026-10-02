import {
  describe,
  expect,
  it,
} from "vitest";

import {
  navigationItems,
} from "../config/navigation";


describe("GreyGuard navigation", () => {
  it("contains unique routes", () => {
    const routes = navigationItems.map(
      (item) => item.path,
    );

    expect(new Set(routes).size).toBe(
      routes.length,
    );
  });

  it("gives every route a visible label", () => {
    for (const item of navigationItems) {
      expect(item.label.trim().length).toBeGreaterThan(
        0,
      );
    }
  });

  it("includes the Live Operations Center", () => {
    expect(
      navigationItems.some(
        (item) => item.path === "/live",
      ),
    ).toBe(true);
  });
});
