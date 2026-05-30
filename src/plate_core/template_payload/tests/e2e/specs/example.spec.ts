import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/login-page';

test.describe('Example Tests', () => {
  test('homepage loads successfully', async ({ page }) => {
    // Navigate to homepage
    const baseUrl = process.env.BASE_URL || 'http://localhost:3000';
    await page.goto(baseUrl);

    // Check that a main heading exists
    const heading = page.locator('h1, h2, [role="heading"]');
    await expect(heading.first()).toBeVisible();
  });

  test('login page renders', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto('/login');

    // Verify login form elements are visible
    await expect(loginPage.emailInput).toBeVisible();
    await expect(loginPage.passwordInput).toBeVisible();
    await expect(loginPage.submitButton).toBeVisible();
  });

  test('login flow can be initiated', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto('/login');

    // Fill in credentials (example values)
    await loginPage.emailInput.fill('demo@example.com');
    await loginPage.passwordInput.fill('demo123');

    // Verify form is filled
    await expect(loginPage.emailInput).toHaveValue('demo@example.com');
    await expect(loginPage.passwordInput).toHaveValue('demo123');
  });
});
