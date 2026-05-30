import { Page } from '@playwright/test';

/**
 * Base Page Object that provides common functionality for all page objects.
 * Subclasses should extend this to share navigation and utility methods.
 */
export class BasePage {
  constructor(protected page: Page) {}

  /**
   * Navigate to a path on the application
   * @param path - URL path (e.g., '/login', '/dashboard')
   */
  async goto(path: string = '/') {
    const baseUrl = process.env.BASE_URL || 'http://localhost:3000';
    await this.page.goto(`${baseUrl}${path}`);
  }

  /**
   * Wait for an element to be visible
   * @param selector - CSS selector or Playwright locator
   */
  async waitForVisible(selector: string) {
    await this.page.locator(selector).waitFor({ state: 'visible' });
  }

  /**
   * Wait for an element to be hidden
   * @param selector - CSS selector or Playwright locator
   */
  async waitForHidden(selector: string) {
    await this.page.locator(selector).waitFor({ state: 'hidden' });
  }

  /**
   * Check if an element is visible
   * @param selector - CSS selector or Playwright locator
   * @returns true if visible, false otherwise
   */
  async isVisible(selector: string): Promise<boolean> {
    return this.page.locator(selector).isVisible();
  }

  /**
   * Get the current URL
   * @returns the current page URL
   */
  getCurrentUrl(): string {
    return this.page.url();
  }
}
