import {
  describe,
  expect,
  it,
} from "vitest";

import {
  connectionLabel,
  parseSseMessage,
  severityClass,
} from "../pages/LiveOperationsPage";


describe("Live Operations helpers", () => {
  it("parses a GreyGuard SSE message", () => {
    const message = parseSseMessage(
      [
        "id: policy-42",
        "event: greyguard-event",
        'data: {"event_id":"policy-42"}',
      ].join("\n"),
    );

    expect(message).toEqual({
      id: "policy-42",
      event: "greyguard-event",
      data: '{"event_id":"policy-42"}',
    });
  });

  it("combines multiline SSE data", () => {
    const message = parseSseMessage(
      [
        "event: heartbeat",
        'data: {"status":',
        'data: "connected"}',
      ].join("\n"),
    );

    expect(message?.event).toBe("heartbeat");
    expect(message?.data).toBe(
      '{"status":\n"connected"}',
    );
  });

  it("ignores messages without data", () => {
    expect(
      parseSseMessage(
        "event: heartbeat\nid: heartbeat-1",
      ),
    ).toBeNull();
  });

  it("maps connection states to clear labels", () => {
    expect(connectionLabel("CONNECTED")).toBe(
      "Live connection active",
    );

    expect(connectionLabel("PAUSED")).toBe(
      "Monitoring paused",
    );

    expect(connectionLabel("ERROR")).toBe(
      "Connection needs attention",
    );
  });

  it("creates normalized severity classes", () => {
    expect(severityClass("CRITICAL")).toBe(
      "live-severity live-severity--critical",
    );
  });
});
