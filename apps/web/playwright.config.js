import {defineConfig} from '@playwright/test';
import {fileURLToPath} from 'node:url';

const remote = process.env.PUZZLE_WEB_URL;
if (remote && (new URL(remote).protocol !== 'https:' || new URL(remote).origin !== remote))
  throw new Error('PUZZLE_WEB_URL must be an HTTPS origin without a trailing slash');

export default defineConfig({
  testDir: './tests', workers: 1, retries: 0, timeout: 45000,
  globalTimeout: 180000,
  use: {baseURL: remote || 'http://127.0.0.1:8792', headless: true},
  webServer: remote ? undefined : {
    command: `${process.env.PUZZLE_PYTHON ? `"${process.env.PUZZLE_PYTHON}"` : 'uv run --no-sync python'} examples/web_server.py --port 8792`,
    cwd: fileURLToPath(new URL('../..', import.meta.url)),
    url: 'http://127.0.0.1:8792', reuseExistingServer: false, timeout: 30000,
  },
});
