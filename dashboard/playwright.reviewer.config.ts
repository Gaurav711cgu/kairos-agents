import { defineConfig } from '@playwright/test';
import path from 'node:path';
const runtime = process.env.KAIROS_REVIEWER_RUNTIME || path.resolve('..', '.runtime/reviewer005');
// Use only the isolated reviewer environment. Authentication state is never exported.
export default defineConfig({
  testDir: './e2e', testMatch: 'reviewer-fullstack.spec.ts', workers: 1, timeout: 60000,
  reporter: [['list'], ['json', { outputFile: path.join(runtime, 'checks/fullstack-browser.json') }]],
  outputDir: path.join(runtime, 'browser/fullstack'),
  use: { baseURL: process.env.KAIROS_REVIEWER_URL || 'http://127.0.0.1:3310',
    viewport: { width: 1440, height: 1000 }, trace: 'off', screenshot: 'off', video: 'off' },
});
