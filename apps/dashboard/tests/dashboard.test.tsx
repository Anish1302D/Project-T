import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { DashboardPage } from "../src/pages/DashboardPage";
import { OFFLINE_DEMO_OVERVIEW } from "../src/services/cloudApi";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("@project-t/dashboard", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    window.localStorage.clear();
  });

  it("renders all 10 required analytics views in offline demo mode", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    act(() => {
      root.render(<DashboardPage initialOverview={OFFLINE_DEMO_OVERVIEW} />);
    });

    const expectedTestIds = [
      "view-original-vs-optimized",
      "view-net-tokens-saved",
      "view-cost-avoided",
      "view-provider-model",
      "view-integration-breakdown",
      "view-usage-trends",
      "view-modes-methods",
      "view-validation-fallbacks",
      "view-benchmark-summaries",
      "view-latency-percentiles"
    ];

    for (const testId of expectedTestIds) {
      expect(container.querySelector(`[data-testid="${testId}"]`)).not.toBeNull();
    }

    expect(container.querySelector('[data-testid="data-source-badge"]')?.textContent).toContain(
      "Offline Preview Fixture"
    );
    expect(container.querySelector('[data-testid="metric-exact-saved"]')?.textContent).toContain(
      "3,680"
    );
    expect(container.querySelector('[data-testid="metric-estimated-saved"]')?.textContent).toContain(
      "1,780"
    );
    expect(container.querySelector('[data-testid="metric-confirmed-saved"]')?.textContent).toContain(
      "1,510"
    );

    act(() => {
      root.unmount();
    });
  });
});
