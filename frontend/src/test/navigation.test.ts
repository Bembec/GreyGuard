import {
  describe,
  expect,
  it,
} from "vitest";

import {
  navigationItems,
  navigationPermission,
} from "../config/navigation";
import { matchesPermission } from "../hooks/usePermission";


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

  it("restricts install-wide pages to install operators, not to an org's platform administrators", () => {
    const orgAdmin = { admin_id: "a", email: "a@x", display_name: "A", role: "PLATFORM_ADMIN" as const, permissions: [] }
    const operator = { ...orgAdmin, install_operator: true }
    for (const path of ["/team", "/observability", "/enterprise-identity", "/abuse-protection"]) {
      const item = navigationItems.find((entry) => entry.path === path)!
      expect(navigationPermission(item)).toEqual({ installOperator: true })
      expect(matchesPermission(orgAdmin, navigationPermission(item))).toBe(false)
      expect(matchesPermission(operator, navigationPermission(item))).toBe(true)
    }
    // Tenant-scoped admin pages stay on the per-org role.
    const exports = navigationItems.find((entry) => entry.path === "/security-exports")!
    expect(matchesPermission(orgAdmin, navigationPermission(exports))).toBe(true)
  });

  it("restricts SIEM exports to platform administrators", () => {
    const item = navigationItems.find((entry) => entry.path === "/security-exports");
    expect(item?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts audit integrity controls to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/audit-integrity")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts communication integrations to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/communication-integrations")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts incident integrations to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/incident-integrations")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts execution isolation to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/execution-isolation")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts isolation operations to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/isolation-operations")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts endpoint telemetry to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/endpoint-telemetry")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts defensive integrations to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/defensive-integrations")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts the non-operational simulation lab to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/simulations")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts universal controls to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/universal-controls")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("restricts capability removal to platform administrators", () => {
    expect(navigationItems.find((entry) => entry.path === "/capability-removals")?.requiredRole).toBe("PLATFORM_ADMIN");
  });
  it("includes the threat and vulnerability register", () => {
    expect(navigationItems.some((entry) => entry.path === "/threat-register")).toBe(true);
  });
});
