// Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
// SPDX-License-Identifier: Apache-2.0

const fs = require('fs')
const path = require('path')

console.log('Copying pre-built backend executable...')

const backendDir = path.join(__dirname, '..', 'backend')
const sourceDir = path.join(__dirname, '..', '..')
const executableName = process.platform === 'win32' ? 'main.exe' : 'main'
const sourceDistDir = path.join(sourceDir, 'dist')
const sourceOnedirPath = path.join(sourceDistDir, 'main')
const sourceOnedirExecutablePath = path.join(sourceOnedirPath, executableName)
const destExecutablePath = path.join(backendDir, executableName)
const sourceConfigDirCandidates = [
  path.join(sourceOnedirPath, 'config'),
  path.join(sourceDistDir, 'config')
]
const destConfigDir = path.join(backendDir, 'config')

function fail(message) {
  console.error(`ERROR: ${message}`)
  process.exit(1)
}

function ensureExists(targetPath, description) {
  if (!fs.existsSync(targetPath)) {
    fail(`${description} not found at: ${targetPath}`)
  }
}

function statOrFail(targetPath, description) {
  ensureExists(targetPath, description)
  return fs.statSync(targetPath)
}

function copyDirectoryContents(srcDir, destDir) {
  const entries = fs.readdirSync(srcDir)
  entries.forEach((entry) => {
    const src = path.join(srcDir, entry)
    const dest = path.join(destDir, entry)
    fs.cpSync(src, dest, { recursive: true, force: true })
  })
}

function resolveSourceConfigDir() {
  return sourceConfigDirCandidates.find((candidate) => fs.existsSync(candidate))
}

function validateCopiedExecutable(sourcePath, destPath) {
  const sourceStats = statOrFail(sourcePath, 'Source backend executable')
  const destStats = statOrFail(destPath, 'Copied backend executable')

  if (sourceStats.size !== destStats.size) {
    fail(
      `Copied backend executable size mismatch. Source=${sourceStats.size}, Destination=${destStats.size}`
    )
  }

  if (sourceStats.mtimeMs !== destStats.mtimeMs) {
    console.warn(
      `Warning: backend executable timestamp differs after copy. Source=${new Date(sourceStats.mtimeMs).toISOString()}, Destination=${new Date(destStats.mtimeMs).toISOString()}`
    )
  }
}

ensureExists(sourceOnedirPath, 'Pre-built backend directory')
ensureExists(sourceOnedirExecutablePath, 'Pre-built backend executable')

if (fs.existsSync(backendDir)) {
  console.log('Cleaning up existing backend directory...')
  fs.rmSync(backendDir, { recursive: true, force: true })
}

fs.mkdirSync(backendDir, { recursive: true })

console.log(`Detected onedir backend build at: ${sourceOnedirPath}`)
copyDirectoryContents(sourceOnedirPath, backendDir)

validateCopiedExecutable(sourceOnedirExecutablePath, destExecutablePath)

if (process.platform !== 'win32') {
  fs.chmodSync(destExecutablePath, 0o755)
}

const executableStats = statOrFail(destExecutablePath, 'Copied backend executable')
const fileSizeInMB = (executableStats.size / (1024 * 1024)).toFixed(2)
console.log(`Copied executable (${fileSizeInMB} MB)`)

const sourceConfigDir = resolveSourceConfigDir()
if (sourceConfigDir) {
  fs.mkdirSync(destConfigDir, { recursive: true })
  copyDirectoryContents(sourceConfigDir, destConfigDir)
  ensureExists(destConfigDir, 'Copied backend config directory')
  const sourceConfigFiles = fs.readdirSync(sourceConfigDir).sort()
  const destConfigFiles = fs.readdirSync(destConfigDir).sort()

  if (sourceConfigFiles.join('|') !== destConfigFiles.join('|')) {
    fail(
      `Copied config files mismatch. Source=${sourceConfigFiles.join(', ')}, Destination=${destConfigFiles.join(', ')}`
    )
  }

  console.log(`Copied ${destConfigFiles.length} config files`)
} else {
  console.log('Warning: No config files found in pre-built backend')
}

console.log('Backend ready for packaging')
