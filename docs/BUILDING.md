# Building installers

This guide covers building installable packages for Windows, Linux, and macOS using `electron-builder`.

## Prerequisites

- Node.js 18+ (20 LTS recommended)
- Python 3.11 (only needed for testing the bundled bootstrap)
- Git
- Platform-specific tooling (see below)

## Building on each platform

`electron-builder` can build for any platform from any host, but **proper code signing requires the matching host OS**. Cross-platform builds are useful for testing; the official releases must be built on each native platform.

### Windows

```powershell
cd app/frontend
npm install
npm run build:win
```

Produces in `app/frontend/release/`:

- `AI-Video-Studio-1.0.0-x64.exe` — NSIS installer
- `AI-Video-Studio-1.0.0-x64-portable.exe` — portable single-file binary
- `win-unpacked/` — raw app directory for testing

**Signing (optional but recommended for production)**

Set environment variables before building:

```powershell
$env:CSC_LINK = "path/to/certificate.pfx"
$env:CSC_KEY_PASSWORD = "your_password"
npm run build:win
```

Or use Azure Key Vault, DigiCert KeyLocker, or similar HSM-backed signing.

### Linux

```bash
cd app/frontend
npm install
npm run build:linux
```

Produces in `app/frontend/release/`:

- `AI-Video-Studio-1.0.0-x64.AppImage` — universal Linux package
- `AI-Video-Studio-1.0.0-x64.deb` — Debian/Ubuntu package
- `linux-unpacked/` — raw app directory

**dpkg requirements (for .deb on non-Debian build hosts):**

```bash
sudo apt install dpkg fakeroot rpm
```

### macOS

Must be built on macOS for proper signing and notarization.

```bash
cd app/frontend
npm install
npm run build:mac
```

Produces:

- `AI-Video-Studio-1.0.0-arm64.dmg` — Apple Silicon
- `AI-Video-Studio-1.0.0-x64.dmg` — Intel
- `AI-Video-Studio-1.0.0-{arch}.zip` — for auto-updater
- `mac/` and `mac-arm64/` — raw .app bundles

**Notarization (required for distribution outside the Mac App Store on macOS 10.15+):**

```bash
export APPLE_ID="your@email.com"
export APPLE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"  # from appleid.apple.com
export APPLE_TEAM_ID="ABCD123456"

# Signing identity (find via `security find-identity -v -p codesigning`)
export CSC_NAME="Developer ID Application: Your Name (TEAMID)"

npm run build:mac
```

`electron-builder` handles signing + notarization stapling automatically when these env vars are set.

## Build everything (CI / triple-platform releases)

```bash
npm run build:all   # macOS, Windows, Linux — must run on macOS for proper mac signing
```

The macOS host can cross-build Linux and Windows packages. Reverse direction (Windows host building macOS) doesn't work cleanly because Apple's signing toolchain is macOS-only.

## What gets bundled

The `extraResources` config in `package.json` includes:

- `installer/` — bootstrap scripts (copied to `resources/installer/`)
- `app/skills/*.json` — all Skill presets
- `app/backend/**/*.py` + `requirements.txt` — the daemon source

What is **not** bundled:

- `app/runtime/` — installed at first launch (Python venv, ComfyUI, models)
- `app/projects/` — user data, kept outside the package

On first launch from a packaged installer, the bootstrap creates `app/runtime/` next to the install location and downloads dependencies. Total install size after first run is ~30 GB depending on model selection.

## Testing the bundled app

After building:

```bash
# Windows
release/win-unpacked/AI\ Video\ Studio.exe

# Linux
release/linux-unpacked/ai-video-studio

# macOS
open release/mac/AI\ Video\ Studio.app
```

Verify:

1. App opens without dev tools
2. SetupScreen runs if `app/runtime/python/` doesn't exist
3. After setup, BootScreen transitions to OnboardingCard then main app
4. Generation completes for a small test project (1 scene, no quality opts)

## Release workflow

1. Bump version in `app/frontend/package.json`
2. Update `CHANGELOG.md` with release notes
3. Tag the commit: `git tag v1.0.0 && git push origin v1.0.0`
4. GitHub Actions builds and uploads installers to the Releases page (config in `.github/workflows/release.yml` — TODO)
5. Manual smoke test on each platform before marking the release public

## Troubleshooting build failures

**`electron-builder` complains about missing icon**  
The build will still succeed and use Electron's default icon. To suppress the warning, add a placeholder PNG/ICO/ICNS to `build/`. See `app/frontend/build/README.md` for icon generation commands.

**Windows installer fails: "Cannot find module"**  
The `files` glob in `package.json` may have excluded something. Add the missing path to the array. Don't rely on `node_modules/**/*` — let electron-builder pick up only what's needed.

**macOS DMG hangs at "Indexing"**  
Spotlight is reindexing the mounted DMG. Wait or eject and remount.

**AppImage fails on Wayland-only systems**  
Older Electron versions force X11. Update to Electron 31+ (already pinned in package.json) which has working Wayland support via `--enable-features=WaylandWindowDecorations`.
