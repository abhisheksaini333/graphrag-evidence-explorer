import { build } from 'esbuild';
import { mkdir, copyFile } from 'node:fs/promises';
await mkdir('dist', { recursive: true });
await build({ entryPoints: ['src/main.tsx'], bundle: true, outfile: 'dist/app.js', format: 'esm', target: 'es2020', minify: true });
await copyFile('index.html', 'dist/index.html');
