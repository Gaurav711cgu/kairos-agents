import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import hooks from 'eslint-plugin-react-hooks';
import a11y from 'eslint-plugin-jsx-a11y';
import react from 'eslint-plugin-react';
export default tseslint.config(
 {ignores:['.next/**','.next-build/**','out/**','build/**','next-env.d.ts']},
 js.configs.recommended,
 ...tseslint.configs.recommended,
 {files:['**/*.{ts,tsx}'],plugins:{'react-hooks':hooks,'jsx-a11y':a11y,react},settings:{react:{version:'detect'}},languageOptions:{globals:{console:'readonly',process:'readonly',fetch:'readonly',URL:'readonly',Response:'readonly',Request:'readonly',AbortSignal:'readonly',crypto:'readonly',setInterval:'readonly',clearInterval:'readonly',window:'readonly',document:'readonly',HTMLElement:'readonly',HTMLInputElement:'readonly',HTMLSelectElement:'readonly',HTMLButtonElement:'readonly',KeyboardEvent:'readonly',navigator:'readonly'}},rules:{...hooks.configs.recommended.rules,...a11y.flatConfigs.recommended.rules,'react/jsx-key':'error','react/jsx-no-target-blank':'error','react/no-unknown-property':'error'}}
);
