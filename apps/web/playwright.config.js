import {defineConfig} from '@playwright/test';
import {fileURLToPath} from 'node:url';

export default defineConfig({
  testDir: './tests', workers: 1, retries: 0, timeout: 45000,
  globalTimeout: 180000,
  use: {baseURL: 'http://127.0.0.1:8792', headless: true},
  webServer: {
    command: `${process.env.PUZZLE_PYTHON ? `"${process.env.PUZZLE_PYTHON}"` : 'uv run --no-sync python'} examples/web_server.py --port 8792`,
    cwd: fileURLToPath(new URL('../..', import.meta.url)),
    url: 'http://127.0.0.1:8792', reuseExistingServer: false, timeout: 30000,
  },
});
