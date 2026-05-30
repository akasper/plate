import { test, expect } from '@playwright/test';

test.describe('Example Failing Test (for demo)', () => {
  test.skip('intentionally fails to demonstrate video capture on failure', async ({ page }) => {
    // This test is intentionally written to fail so that you can see how Playwright
    // captures videos and traces when tests fail. In CI and local test runs, you'll
    // see videos retained in the test-results/ directory.
    //
    // To run this test:
    //   npx playwright test tests/e2e/specs/failing-example.spec.ts
    //
    // Then view the video in test-results/

    const baseUrl = process.env.BASE_URL || 'http://localhost:3000';
    await page.goto(baseUrl);

    // This assertion will fail, triggering video capture
    await expect(page.locator('h1')).toContainText('Intentionally Failing Text That Does Not Exist');
  });
});
