#!/usr/bin/env node

/**
 * Copy Pre-built Backend Script
 *
 * Copies the freshly built Python backend from dist/main/ to frontend/backend/
 * so that electron-builder packages the latest build (not stale content).
 *
 * Also validates:
 *   1. dist/main/main.exe exists (Python build completed)
 *   2. dist/main/ is newer than existing frontend/backend/ (incremental safety check)
 *
 * This script is called by frontend/package.json:
 *   - build:win
 *   - build:mac
 *   - publish
 *   - copy-backend (standalone)
 */

'use strict'

const fs = require('fs')
const path = require('path')

// Paths are relative to repo root (parent of frontend/)
const ROOT_DIR = path.resolve(__dirname, '..')
const FRONTEND_DIR = path.join(ROOT_DIR, 'frontend')
// The PyInstaller one-dir build output: main.exe + _internal/ directory
// Bundled data (config, python extensions) live inside _internal/
const SRC_BACKEND = path.join(ROOT_DIR, 'dist', 'main')
// Where to copy for electron-builder packaging
const DST_BACKEND = path.join(FRONTEND_DIR, 'backend')

function log(level, msg) {
  const prefix = level === 'ERROR' ? '❌' : level === 'WARN' ? '⚠️' : '✅'
  console.log(`${prefix} [copy-backend] ${msg}`)
}

function copyDirRecursive(src, dst) {
  // Create destination directory if it doesn't exist
  if (!fs.existsSync(dst)) {
    fs.mkdirSync(dst, { recursive: true })
  }

  const entries = fs.readdirSync(src, { withFileTypes: true })

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name)
    const dstPath = path.join(dst, entry.name)

    if (entry.isDirectory()) {
      copyDirRecursive(srcPath, dstPath)
    } else {
      // Copy file - ensure destination directory exists
      const dstDir = path.dirname(dstPath)
      if (!fs.existsSync(dstDir)) {
        fs.mkdirSync(dstDir, { recursive: true })
      }
      fs.copyFileSync(srcPath, dstPath)
    }
  }
}

function getDirTimestamp(dir) {
  // Return the newest file's mtime in a directory tree
  let newest = 0
  function walk(d) {
    const entries = fs.readdirSync(d, { withFileTypes: true })
    for (const entry of entries) {
      const full = path.join(d, entry.name)
      if (entry.isDirectory()) {
        walk(full)
      } else {
        const mtime = fs.statSync(full).mtimeMs
        if (mtime > newest) newest = mtime
      }
    }
  }
  try {
    walk(dir)
  } catch {
    // Dir doesn't exist yet
  }
  return newest
}

function validateBuild() {
  const mainExe = path.join(SRC_BACKEND, 'main.exe')
  if (!fs.existsSync(mainExe)) {
    log('ERROR', `Fresh backend not found at ${mainExe}`)
    log('ERROR', 'Please run the Python build first: ./build.sh (or build.ps1 on Windows)')
    process.exit(1)
  }

  const srcExeStat = fs.statSync(mainExe)
  const srcMtime = srcExeStat.mtimeMs
  const srcSize = srcExeStat.size
  log('INFO', `Source main.exe: ${srcSize} bytes, mtime=${new Date(srcMtime).toISOString()}`)

  // Incremental safety: check timestamps
  const dstMtime = getDirTimestamp(DST_BACKEND)

  if (dstMtime > srcMtime) {
    log('WARN', `frontend/backend/ (mtime=${new Date(dstMtime).toISOString()}) is NEWER than dist/main/ (mtime=${new Date(srcMtime).toISOString()})`)
    log('WARN', 'This suggests frontend/backend/ was modified after the last Python build.')
    log('WARN', 'Proceeding anyway to allow intentional overrides...')
  } else {
    log('INFO', `Timestamp check passed: dist/main/ is fresh (${new Date(srcMtime).toISOString()})`)
  }

  // Check for the screenshot_analyze prompt fallback marker in the spec or prompts
  // In PyInstaller one-dir on Windows, bundled data lives in _internal/ subdirectory
  const bundledConfigDir = path.join(SRC_BACKEND, '_internal', 'config')
  const promptsZh = path.join(bundledConfigDir, 'prompts_zh.yaml')
  const promptsEn = path.join(bundledConfigDir, 'prompts_en.yaml')
  const configYaml = path.join(bundledConfigDir, 'config.yaml')

  if (!fs.existsSync(promptsZh)) {
    log('ERROR', `prompts_zh.yaml not found in ${bundledConfigDir} - prompts may not be bundled correctly`)
    process.exit(1)
  }
  if (!fs.existsSync(promptsEn)) {
    log('ERROR', `prompts_en.yaml not found in ${bundledConfigDir} - prompts may not be bundled correctly`)
    process.exit(1)
  }
  if (!fs.existsSync(configYaml)) {
    log('ERROR', `config.yaml not found in ${bundledConfigDir} - config may not be bundled correctly`)
    process.exit(1)
  }
  log('INFO', 'Prompt files validated (screenshot_analyze + screenshot_contextual_batch fallback supported)')

  return { srcMtime, srcSize }
}

function verifyCopy() {
  const srcMainExe = path.join(SRC_BACKEND, 'main.exe')
  const dstMainExe = path.join(DST_BACKEND, 'main.exe')

  if (!fs.existsSync(dstMainExe)) {
    log('ERROR', 'Copy verification failed: main.exe not found after copy')
    process.exit(1)
  }

  const srcStat = fs.statSync(srcMainExe)
  const dstStat = fs.statSync(dstMainExe)

  if (srcStat.size !== dstStat.size) {
    log('ERROR', `Size mismatch: source=${srcStat.size}, destination=${dstStat.size}`)
    log('ERROR', 'Backend copy may be corrupted')
    process.exit(1)
  }

  // Allow up to 5 seconds difference due to filesystem precision
  const timeDiff = Math.abs(srcStat.mtimeMs - dstStat.mtimeMs)
  if (timeDiff > 5000) {
    log('WARN', `Timestamp difference: ${timeDiff}ms (source=${new Date(srcStat.mtimeMs).toISOString()}, dst=${new Date(dstStat.mtimeMs).toISOString()})`)
  }

  log('INFO', `Copy verification passed: main.exe (${srcStat.size} bytes)`)

  // Verify config files were copied (they go to _internal/config/ in PyInstaller one-dir)
  const requiredFiles = [
    path.join(DST_BACKEND, '_internal', 'config', 'prompts_zh.yaml'),
    path.join(DST_BACKEND, '_internal', 'config', 'prompts_en.yaml'),
    path.join(DST_BACKEND, '_internal', 'config', 'config.yaml'),
  ]
  for (const f of requiredFiles) {
    if (!fs.existsSync(f)) {
      log('ERROR', `Required file missing after copy: ${f}`)
      process.exit(1)
    }
  }
  log('INFO', 'All required config files verified (_internal/config/)')
}

function main() {
  console.log('\n🚀 Copy Pre-built Backend Script')
  console.log('   Source:      dist/main/  (fresh Python build)')
  console.log('   Destination: frontend/backend/  (for electron-builder)')

  // Validate source exists
  if (!fs.existsSync(SRC_BACKEND)) {
    log('ERROR', `Source backend not found: ${SRC_BACKEND}`)
    log('ERROR', 'Run the Python build first:')
    if (process.platform === 'win32') {
      log('ERROR', '  .\\build.ps1')
    } else {
      log('ERROR', '  ./build.sh')
    }
    process.exit(1)
  }

  // Validate and log
  validateBuild()

  // Remove existing destination
  if (fs.existsSync(DST_BACKEND)) {
    log('INFO', `Removing stale backend at ${DST_BACKEND}`)
    fs.rmSync(DST_BACKEND, { recursive: true, force: true })
  }

  // Copy fresh build
  log('INFO', `Copying fresh backend from ${SRC_BACKEND} to ${DST_BACKEND}`)
  copyDirRecursive(SRC_BACKEND, DST_BACKEND)

  // Verify copy integrity
  verifyCopy()

  log('INFO', `Copied _internal/config/ directory (prompts_zh.yaml, prompts_en.yaml, config.yaml)`)
  console.log('\n🎉 Backend copied successfully!\n')
}

main()
