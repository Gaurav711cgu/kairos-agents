import {defineConfig} from '@playwright/test';
import path from 'node:path';
const runtime=process.env.KAIROS_REVIEWER_RUNTIME;
if(!runtime)throw new Error('Select the owned live reviewer runtime explicitly.');
export default defineConfig({
  testDir:'./e2e',testMatch:'reviewer-execution.spec.ts',workers:1,timeout:660000,
  reporter:[['list'],['json',{outputFile:path.join(runtime,'checks/execution-browser.json')}]],
  outputDir:path.join(runtime,'browser/execution'),
  use:{baseURL:process.env.KAIROS_REVIEWER_URL||'http://127.0.0.1:3310',viewport:{width:1440,height:1000},
    trace:'off',screenshot:'off',video:'off'},
});
