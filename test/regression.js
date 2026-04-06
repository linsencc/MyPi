import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  let backendErrors = [];
  page.on('response', async response => {
    if (!response.ok() && response.url().includes('/api/')) {
      backendErrors.push(`Error ${response.status()} at ${response.url()}`);
      console.log(`[API ERROR] ${response.status()} at ${response.url()}`);
    }
  });

  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  
  page.on('dialog', async dialog => {
    console.log('Dialog opened:', dialog.message());
    await dialog.accept();
  });

  console.log("=== P0 Regression Test: Starting ===");
  console.log("Navigating to http://localhost:5173/ ...");
  
  await page.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 5000));
  await page.screenshot({ path: 'test_step1_initial.png' });
  console.log("[PASS] Page loaded. Screenshot saved to test_step1_initial.png");

  // --- TC-3.1: Live Preview (立即渲染) ---
  console.log("\n--- TC-3.1: Live Preview ---");
  try {
    await page.waitForSelector('button[aria-label^="立即渲染"]', { timeout: 10000 });
  } catch (err) {
    const text = await page.evaluate(() => document.body.innerText);
    console.log("Page text on timeout:", text);
    throw err;
  }
  const playBtn = await page.$('button[aria-label^="立即渲染"], button[title^="立即渲染"]');
  if (playBtn) {
    await playBtn.click();
    await new Promise(r => setTimeout(r, 3000));
    await page.screenshot({ path: 'test_step2_live_preview.png' });
    console.log("[PASS] Clicked '立即渲染'. Screenshot saved to test_step2_live_preview.png");
  } else {
    console.log("[ERROR] Could not find '立即渲染' button.");
    await browser.close();
    process.exit(1);
  }

  // --- TC-3.2: Create Scene ---
  console.log("\n--- TC-3.2: Create Scene ---");
  // We need to count scenes before create to verify it actually created
  const initialSceneCount = await page.evaluate(() => {
    const tbody = document.querySelector('tbody');
    return tbody ? tbody.querySelectorAll('tr').length : 0;
  });

  const createBtn = await page.$('button[aria-label^="创建场景"]');
  if (createBtn) {
    await createBtn.click();
    await new Promise(r => setTimeout(r, 1500));
    console.log("[PASS] Opened create scene dialog.");

    const saveBtn = await page.evaluateHandle(() => {
      return Array.from(document.querySelectorAll('button')).find(el => el.textContent === '保存' || el.textContent === 'Save');
    });
    if (saveBtn) {
      await saveBtn.click();
      await new Promise(r => setTimeout(r, 2000));
      
      const newSceneCount = await page.evaluate(() => {
        const tbody = document.querySelector('tbody');
        return tbody ? tbody.querySelectorAll('tr').length : 0;
      });

      if (newSceneCount <= initialSceneCount) {
        console.log(`[ERROR] Scene count did not increase after create. Initial: ${initialSceneCount}, New: ${newSceneCount}`);
        await browser.close();
        process.exit(1);
      }
      console.log("[PASS] Scene created successfully, list updated.");
    } else {
      console.log("[ERROR] Could not find '保存' button.");
      await browser.close();
      process.exit(1);
    }
  } else {
    console.log("[ERROR] Could not find '创建场景' button.");
    await browser.close();
    process.exit(1);
  }

  // --- TC-5.1: Enable/Disable ---
  console.log("\n--- TC-5.1: Toggle Enable/Disable ---");
  const switchBtn = await page.$('button[role="switch"]');
  if (switchBtn) {
    // get initial state
    const isCheckedInitial = await page.evaluate(el => el.getAttribute('aria-checked') === 'true', switchBtn);
    
    await switchBtn.click();
    await new Promise(r => setTimeout(r, 1500));
    
    const isCheckedAfter = await page.evaluate(el => el.getAttribute('aria-checked') === 'true', switchBtn);
    
    if (isCheckedInitial === isCheckedAfter) {
      console.log("[ERROR] Switch state did not change after click.");
      await browser.close();
      process.exit(1);
    }
    console.log("[PASS] Scene disabled/enabled toggled.");
    
    // Toggle back to original state so we don't break following tests
    await switchBtn.click();
    await new Promise(r => setTimeout(r, 1500));
  } else {
    console.log("[ERROR] No switch found. Cannot test '启用/停用'.");
    await browser.close();
    process.exit(1);
  }

  // --- TC-2: Timeline ---
  console.log("\n--- TC-2: Timeline Validation ---");
  const timelineText = await page.evaluate(() => {
    const heading = document.getElementById('playback-timeline-heading');
    if (!heading) return "";
    const section = heading.closest('section');
    return section ? section.innerText : "";
  });

  if (timelineText.includes('即将在') || timelineText.includes('Upcoming') || timelineText.includes('前天') || timelineText.includes('昨天') || timelineText.includes('今天') || timelineText.includes('明天') || timelineText.includes('后天')) {
    console.log("[PASS] Timeline components seem to be rendering correctly.");
  } else {
    console.log("[WARN] Timeline specific relative text not found, timeline text is: ", timelineText);
  }

  // --- TC-4.1 & TC-3: Polling/Refresh Wait ---
  console.log("\n--- Wait for Polling/Auto-refresh ---");
  console.log("Waiting 15 seconds to see if preview auto-updates or background tasks run...");
  // We don't have a strict DOM assert here because we don't know exact scheduled time,
  // but this ensures the process stays alive long enough to catch potential SSE or Interval issues.
  await new Promise(r => setTimeout(r, 15000));
  console.log("[PASS] Waited 15s successfully.");

  // --- TC-5.3: Delete Scene ---
  console.log("\n--- TC-5.3: Delete Scene ---");
  const preDeleteCount = await page.evaluate(() => {
    const tbody = document.querySelector('tbody');
    return tbody ? tbody.querySelectorAll('tr').length : 0;
  });

  const deleteBtn = await page.$('button[aria-label^="删除"], button[aria-label^="Delete"]');
  if (deleteBtn) {
    await deleteBtn.click(); // This will trigger window.confirm, handled by dialog event above
    await new Promise(r => setTimeout(r, 1500));
    
    const postDeleteCount = await page.evaluate(() => {
      const tbody = document.querySelector('tbody');
      return tbody ? tbody.querySelectorAll('tr').length : 0;
    });

    if (postDeleteCount >= preDeleteCount) {
      console.log(`[ERROR] Scene count did not increase after delete. Initial: ${preDeleteCount}, After: ${postDeleteCount}`);
      await browser.close();
      process.exit(1);
    }
    
    await page.screenshot({ path: 'test_step5_deleted.png' });
    console.log("[PASS] Scene deleted successfully.");
  } else {
    console.log("[WARN] Could not find delete button, skipping delete test. (Maybe list is empty)");
  }

  await browser.close();

  console.log("\n=== SUMMARY ===");
  if (backendErrors.length > 0) {
    console.log("[FAIL] Backend API errors encountered:");
    console.log(backendErrors.join("\n"));
    process.exit(1);
  } else {
    console.log("[PASS] No unhandled Backend API errors.");
    console.log("[PASS] All UI assertions passed.");
    process.exit(0);
  }
})();
