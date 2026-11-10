// Scores every generated page with fixed checks, in a real browser. Run by Playwright: async (page) => { ... }.
// Each check is one point. The same checks are applied to every model and set-up.
async (page) => {
  const base = "http://127.0.0.1:8765/out/";
  const shots = "/Users/p3wrky/Desktop/camr-repo/.playwright-mcp/web/";
  const results = [];
  // A page may answer bad input with an alert box. It is closed so the checks can go on; using one is not counted against the page.
  page.on("dialog", (dialog) => dialog.dismiss().catch(() => {}));
  const text = async (sel) => (await page.locator(sel).first().textContent({ timeout: 1500 }).catch(() => "")) || "";
  const fill = async (sel, v) => page.locator(sel).first().fill(String(v), { timeout: 1500 }).catch(() => {});
  const click = async (sel) => page.locator(sel).first().click({ timeout: 1500 }).catch(() => {});
  const has = async (ids) => { for (const id of ids) { if (await page.locator("#" + id).count() === 0) return false; } return true; };
  const noSideScroll = async () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  const digits = (s) => s.replace(/[^0-9]/g, "");
  const visible = async (sel) => page.locator(sel).first().isVisible().catch(() => false);

  const tests = {
    fare: async (c) => {
      c.ids = await has(["distance", "passengers", "period", "calculate", "total", "each"]);
      await fill("#distance", 10); await fill("#passengers", 4); await page.locator("#period").selectOption("peak").catch(() => {}); await click("#calculate");
      c.example_total = digits(await text("#total")) === "255"; c.example_each = digits(await text("#each")) === "64";
      c.kes_format = /KES\s?255/.test(await text("#total"));
      await fill("#distance", 7); await fill("#passengers", 3); await page.locator("#period").selectOption("offpeak").catch(() => {}); await click("#calculate");
      c.second_total = digits(await text("#total")) === "134"; c.second_each = digits(await text("#each")) === "45";
      await fill("#distance", ""); await click("#calculate");
      c.invalid_message = (await text("#message")).trim().length > 0;
      c.invalid_no_result = digits(await text("#total")) !== "134";
    },
    queue: async (c) => {
      c.ids = await has(["name", "reason", "add", "queue", "count", "next", "now"]);
      await fill("#name", "Amina"); await page.locator("#reason").selectOption({ label: "Consultation" }).catch(() => {}); await click("#add");
      await fill("#name", "Brian"); await page.locator("#reason").selectOption({ label: "Lab" }).catch(() => {}); await click("#add");
      c.two_listed = await page.locator("#queue li").count() === 2;
      const first = await text("#queue li");
      c.order_and_reason = first.includes("Amina") && first.includes("Consultation");
      c.count_two = (await text("#count")).trim() === "2";
      await fill("#name", "   "); await click("#add");
      c.empty_not_added = await page.locator("#queue li").count() === 2;
      await click("#next");
      c.next_shows = (await text("#now")).includes("Amina");
      c.next_removes = await page.locator("#queue li").count() === 1 && (await text("#count")).trim() === "1";
      c.saved = await page.evaluate(() => localStorage.getItem("clinic-queue") !== null);
      await page.reload(); await page.waitForTimeout(300);
      c.restored = await page.locator("#queue li").count() === 1 && (await text("#now")).includes("Amina") && (await text("#queue li")).includes("Brian");
    },
    landing: async (c) => {
      c.ids = await has(["menu", "nav", "hero", "features", "pricing", "billing", "price"]);
      c.three_features = await page.locator("#features .feature").count() === 3;
      c.monthly = /KES\s?500\b/.test(await text("#price"));
      await page.locator("#billing").first().check({ timeout: 1500, force: true }).catch(() => {});
      c.yearly = /KES\s?5,000/.test(await text("#price"));
      await page.locator("#billing").first().uncheck({ timeout: 1500, force: true }).catch(() => {});
      c.monthly_again = /KES\s?500\b/.test(await text("#price")) && !/5,000/.test(await text("#price"));
      const html = await page.content();
      c.no_filler_or_images = !/lorem ipsum/i.test(html) && (await page.locator("img").count()) === 0;
      c.nav_shown_wide = await visible("#nav");
      await page.setViewportSize({ width: 375, height: 800 }); await page.reload(); await page.waitForTimeout(300);
      c.nav_hidden_narrow = !(await visible("#nav"));
      await click("#menu"); c.menu_opens = await visible("#nav");
      await click("#menu"); c.menu_closes = !(await visible("#nav"));
    },
  };

  for (const task of ["fare", "queue", "landing"]) {
    for (const kind of ["local", "cloud"]) {
      for (const setup of ["alone", "engine", "full"]) {
        const name = `${task}-${kind}-${setup}`;
        const probe = await page.request.get(base + name + ".html");
        if (probe.status() !== 200) continue;
        const source = await probe.text();
        const errors = [];
        const outside = [];
        const onError = (e) => errors.push(String(e).slice(0, 120));
        const onConsole = (m) => { if (m.type() === "error" && !m.text().includes("Failed to load resource")) errors.push(m.text().slice(0, 120)); };
        const onRequest = (r) => { if (!r.url().startsWith("http://127.0.0.1:8765") && !r.url().startsWith("data:")) outside.push(r.url().slice(0, 80)); };
        await page.setViewportSize({ width: 1200, height: 900 });
        // Every page shares one address, so what the last page saved is cleared before this one is watched for errors.
        await page.goto("about:blank"); await page.goto(base + "blank.html"); await page.evaluate(() => localStorage.clear());
        page.on("pageerror", onError); page.on("console", onConsole); page.on("request", onRequest);
        await page.goto(base + name + ".html"); await page.waitForTimeout(300);
        await page.screenshot({ path: shots + name + ".png" });
        const c = {};
        c.complete_file = /<\/html>\s*$/i.test(source.trim());
        c.viewport_tag = await page.locator('meta[name="viewport"]').count() > 0;
        try { await tests[task](c); } catch (e) { c.crashed = false; errors.push("check stopped: " + String(e).slice(0, 100)); }
        await page.setViewportSize({ width: 375, height: 800 }); await page.waitForTimeout(200);
        c.no_side_scroll_on_phone = await noSideScroll();
        await page.screenshot({ path: shots + name + "-phone.png" });
        c.no_script_errors = errors.length === 0;
        c.no_outside_files = outside.length === 0;
        page.off("pageerror", onError); page.off("console", onConsole); page.off("request", onRequest);
        const passed = Object.values(c).filter(Boolean).length;
        results.push({ name, passed, of: Object.keys(c).length, failed: Object.keys(c).filter((k) => !c[k]), errors: errors.slice(0, 3) });
      }
    }
  }
  return JSON.stringify(results);
}
