import { expect, test } from "@playwright/test";

test.describe("gallery", () => {
  test("shows every card and filters without a round trip", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("163");

    const tiles = page.locator("[data-tile]");
    await expect(tiles).toHaveCount(163);

    // filtering is client side, so nothing may go over the wire
    let requests = 0;
    page.on("request", (r) => {
      if (r.url().includes("/api/")) requests += 1;
    });

    await page.getByRole("button", { name: /Developer/ }).click();
    await expect(tiles.first()).toBeVisible();
    const developerCount = await tiles.count();
    expect(developerCount).toBeGreaterThan(10);
    expect(developerCount).toBeLessThan(163);

    await page.getByPlaceholder("suchen").fill("terminal");
    await expect(page.locator("[data-tile='terminal']")).toBeVisible();
    expect(requests).toBe(0);
  });

  test("says so when nothing matches", async ({ page }) => {
    await page.goto("/");
    await page.getByPlaceholder("suchen").fill("zzzznope");
    await expect(page.getByText(/Keine Karte passt/)).toBeVisible();
    await page.getByRole("button", { name: /zuruecksetzen/ }).click();
    await expect(page.locator("[data-tile]")).toHaveCount(163);
  });

  test("a card page links into the studio with its own spec", async ({ page }) => {
    await page.goto("/card/terminal");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("terminal");

    await page.getByRole("link", { name: /Im Studio oeffnen/ }).click();
    await expect(page).toHaveURL(/\/studio\?s=/);
    await expect(page.getByLabel("Name")).toHaveValue("Alperen Adatepe");
  });
});

test.describe("studio", () => {
  test("renders the card and follows an edit", async ({ page }) => {
    await page.goto("/studio");

    const stage = page.locator("svg[role='img']");
    await expect(stage).toBeVisible();
    const before = await stage.getAttribute("aria-label");

    await page.getByLabel("Name").fill("Mira Halvorsen");
    // the preview holds still until the new geometry arrives, then swaps
    await expect
      .poll(async () => (await page.locator("svg[role='img'] path").count()) > 0, {
        timeout: 20_000,
      })
      .toBe(true);
    expect(before).toContain("classic");

    // the url carries the whole card
    await expect(page).toHaveURL(/\?s=/);
    const url = page.url();
    await page.goto(url);
    await expect(page.getByLabel("Name")).toHaveValue("Mira Halvorsen");
  });

  test("reports a print problem at the field that caused it", async ({ page }) => {
    await page.goto("/studio");
    await page.getByLabel("QR-Ziel").fill(`https://example.com/${"x".repeat(90)}`);

    await expect(page.getByText(/QR-Modul/).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/unter dem Minimum/).first()).toBeVisible();

    // and the download is refused while the error stands
    await expect(page.getByRole("button", { name: "3MF" })).toBeDisabled();
    await expect(page.getByText(/Der Druck-Check meldet einen Fehler/)).toBeVisible();
  });

  test("a warning does not block the download", async ({ page }) => {
    await page.goto("/studio");
    await page.getByLabel("QR-Ziel").fill("https://linkedin.com/in/mirahalvorsen");
    await expect(page.getByText(/unter dem Zielwert/).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: "3MF" })).toBeEnabled();
  });

  test("hands out a 3MF a slicer can open", async ({ page }) => {
    await page.goto("/studio");
    await expect(page.locator("svg[role='img']")).toBeVisible({ timeout: 20_000 });

    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 45_000 }),
      page.getByRole("button", { name: "3MF" }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/^card-[0-9a-f]{16}\.3mf$/);

    const path = await download.path();
    const { readFileSync } = await import("node:fs");
    const head = readFileSync(path).subarray(0, 2).toString();
    expect(head).toBe("PK"); // a 3MF is a zip
  });

  test("switching to 3D keeps the card and loads three.js on demand", async ({
    page,
  }) => {
    await page.goto("/studio");
    await expect(page.locator("svg[role='img']")).toBeVisible({ timeout: 20_000 });

    await page.getByRole("button", { name: "3D" }).click();
    await expect(page.locator("canvas")).toBeVisible({ timeout: 30_000 });

    await page.getByRole("button", { name: "2D" }).click();
    await expect(page.locator("svg[role='img']")).toBeVisible();
  });

  test("resets to the preset", async ({ page }) => {
    await page.goto("/studio");
    await page.getByRole("button", { name: "eckig" }).click();
    const reset = page.getByRole("button", { name: /Auf classic zuruecksetzen/ });
    await expect(reset).toBeVisible();
    await reset.click();
    await expect(reset).toBeHidden();
  });
});

test.describe("layout", () => {
  test("nothing scrolls sideways", async ({ page }) => {
    for (const path of ["/", "/card/tree", "/studio"]) {
      await page.goto(path);
      await page.waitForTimeout(500);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, path).toBeLessThanOrEqual(1);
    }
  });

  test("the theme toggle sticks across a reload", async ({ page }) => {
    await page.goto("/");
    const toggle = page.getByRole("button", { name: /wechseln/ });
    const label = await toggle.textContent();
    await toggle.click();
    await page.reload();
    await expect(page.getByRole("button", { name: /wechseln/ })).not.toHaveText(
      label ?? "",
    );
  });
});
