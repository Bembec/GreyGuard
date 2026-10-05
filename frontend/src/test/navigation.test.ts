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

  it("includes the security Notification Center", () => {
    expect(navigationItems.some((item) => item.path === "/notifications")).toBe(true);
  });

  it("includes restricted machine identity management", () => {
    const item = navigationItems.find((entry) => entry.path === "/service-accounts");
    expect(item?.requiredRole).toBe("PLATFORM_ADMIN");
  });

  it("includes compliance evidence exports", () => {
    expect(navigationItems.some((item) => item.path === "/compliance")).toBe(true);
  });

  it("restricts abuse controls to platform administrators", () => {
    const item = navigationItems.find((entry) => entry.path === "/abuse-protection");
    expect(item?.requiredRole).toBe("PLATFORM_ADMIN");
  });

  it("restricts SIEM exports to platform administrators", () => {
    const item = navigationItems.find((entry) => entry.path === "/security-exports");
    expect(item?.requiredRole).toBe("PLATFORM_ADMIN");
  });
});
