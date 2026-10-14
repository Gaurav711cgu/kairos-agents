import { defineConfig } from '@playwright/test';
const testPython = process.env.KAIROS_TEST_PYTHON || '.venv/bin/python';
const quotedPython = "'" + testPython.replaceAll("'", "'\\''") + "'";
export default defineConfig({
  testDir:'./e2e',testMatch:['workbench.spec.ts','public.spec.ts'],workers:1,timeout:30000,reporter:[['list']],
  use:{baseURL:'http://127.0.0.1:3104',viewport:{width:1440,height:1000},trace:'off'},
  outputDir:'.playwright-results',
  webServer:[
    {command:'cd .. && '+quotedPython+' scripts/browser_fixture.py',url:'http://127.0.0.1:8195/docs',reuseExistingServer:false},
    {command:'KAIROS_EVIDENCE_MODE=live KAIROS_API_URL=http://127.0.0.1:8195 npm run dev -- --hostname 127.0.0.1 --port 3104',url:'http://127.0.0.1:3104/workbench',reuseExistingServer:false,timeout:120000},
  ],
});
