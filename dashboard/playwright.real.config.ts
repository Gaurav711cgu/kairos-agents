import {defineConfig} from '@playwright/test';
const testPython = process.env.KAIROS_TEST_PYTHON || '.venv/bin/python';
const quotedPython = "'" + testPython.replaceAll("'", "'\\''") + "'";
export default defineConfig({testDir:'./e2e',testMatch:'identity.spec.ts',workers:1,timeout:60000,reporter:[['list']],
  use:{baseURL:'http://127.0.0.1:3105',trace:'off',screenshot:'off',video:'off'},outputDir:'.playwright-results-real',
  webServer:[{command:'cd .. && PYTHONPATH=. '+quotedPython+' scripts/browser_identity_fixture.py',url:'http://127.0.0.1:8106/api/health',reuseExistingServer:false,timeout:120000},
    {command:'KAIROS_EVIDENCE_MODE=live KAIROS_NEXT_BUILD_DIR=.next-identity KAIROS_API_URL=http://127.0.0.1:8106 KAIROS_AUTH_LOGIN_URL=http://127.0.0.1:8106/api/auth/login KAIROS_WEB_ORIGIN=http://127.0.0.1:3105 npm run dev -- --hostname 127.0.0.1 --port 3105',url:'http://127.0.0.1:3105/workbench',reuseExistingServer:false,timeout:120000}]
});
