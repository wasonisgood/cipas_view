import { mkdirSync, copyFileSync, existsSync, rmSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

const rootDir = process.cwd();
const distDir = resolve(rootDir, 'dist');

if (existsSync(distDir)) {
  rmSync(distDir, { recursive: true, force: true });
}
mkdirSync(distDir, { recursive: true });

// Copy dashboard_app.html as index.html and dashboard.html
copyFileSync(resolve(rootDir, 'dashboard_app.html'), resolve(distDir, 'index.html'));
copyFileSync(resolve(rootDir, 'dashboard_app.html'), resolve(distDir, 'dashboard.html'));

// Copy other html pages
const otherPages = ['stats.html', 'meetings_dashboard.html'];
for (const page of otherPages) {
  const p = resolve(rootDir, page);
  if (existsSync(p)) {
    copyFileSync(p, resolve(distDir, page));
  }
}

// Copy data files
const dataFiles = [
  'cipas_full_data.js',
  'cipas_all_steps.js',
  'cipas_all_steps.json',
  'cipas_data.js',
  'cipas_data.json',
  'meetings_data.js',
  'meetings_data.json'
];

for (const file of dataFiles) {
  const p = resolve(rootDir, file);
  if (existsSync(p)) {
    copyFileSync(p, resolve(distDir, file));
    console.log(`[Build] Copied ${file}`);
  } else {
    console.warn(`[Build] Warning: ${file} not found`);
  }
}

console.log('[Build] Completed building cipas_view to dist/');
