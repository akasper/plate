import { BasePage } from './base-page';

/**
 * Login page object that encapsulates selectors and actions for the login page.
 * This is an example page object showing the Page Object Model pattern.
 */
export class LoginPage extends BasePage {
  // Selectors
  readonly emailInput = this.page.locator('input[type="email"]');
  readonly passwordInput = this.page.locator('input[type="password"]');
  readonly submitButton = this.page.locator('button[type="submit"]');

  /**
   * Perform a login action
   * @param email - User's email address
   * @param password - User's password
   */
  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();

    // Wait for navigation after login
    await this.page.waitForNavigation();
  }

  /**
   * Get error message if login fails
   * @returns error message text
   */
  async getErrorMessage(): Promise<string | null> {
    const errorLocator = this.page.locator('[role="alert"]');
    if (await errorLocator.isVisible()) {
      return errorLocator.textContent();
    }
    return null;
  }
}
