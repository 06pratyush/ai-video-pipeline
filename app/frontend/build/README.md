# Build Resources

This directory holds platform-specific assets that electron-builder picks up automatically when packaging.

## Required Files

| File | Used By | Specs |
|------|---------|-------|
| `icon.ico` | Windows installer + app icon | 256×256 (multi-resolution .ico, includes 16/32/48/64/128/256) |
| `icon.icns` | macOS app bundle | macOS icon set; generate via `iconutil` from an `icon.iconset` folder containing 16/32/64/128/256/512/1024 sizes (+ @2x variants) |
| `icon.png` | Linux AppImage / .deb | 512×512 PNG, transparent background |
| `entitlements.mac.plist` | macOS code signing | Already provided — grants JIT, network, file access |

## Optional Files

| File | Used By | Specs |
|------|---------|-------|
| `installer-header.bmp`   | NSIS Windows installer | 150×57 BMP |
| `installer-sidebar.bmp`  | NSIS Windows installer | 164×314 BMP |
| `background.png`         | macOS DMG               | 540×380 PNG |

## Generating Icons

Start with a single 1024×1024 PNG of the app logo (`source.png`):

### Windows .ico
```bash
# ImageMagick:
magick convert source.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

### macOS .icns
```bash
mkdir icon.iconset
sips -z 16 16     source.png --out icon.iconset/icon_16x16.png
sips -z 32 32     source.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     source.png --out icon.iconset/icon_32x32.png
sips -z 64 64     source.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   source.png --out icon.iconset/icon_128x128.png
sips -z 256 256   source.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   source.png --out icon.iconset/icon_256x256.png
sips -z 512 512   source.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   source.png --out icon.iconset/icon_512x512.png
cp source.png                  icon.iconset/icon_512x512@2x.png
iconutil -c icns icon.iconset
```

### Linux .png
Just resize the source to 512×512 — that's it.

## Until Icons Are Added

electron-builder falls back to a generic Electron icon. Builds will still succeed.
