# Changelog

All notable changes to iGnition are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.2.0] - 2026-02-22

### Added
- **Live running status** — app cards show a green dot and a Stop button while the app is running.
- **App search** — filter your app list by name using the search box in the toolbar.
- **Popular Apps button** — always visible in the toolbar, not just when the list is empty.
- **Active profile shown on Apps page** — small indicator below the page title shows which profile you're editing.
- **More apps in the quick-add list** — OBS Studio, Logitech G HUB, RTSS, Helicorsa, Sim Dashboard Server, Garage 61, Pitskill, SRS.
- **Icon cache** — app icons load instantly on restart instead of being fetched every time.

### Fixed
- Changing the trigger mode (UI / Race) no longer overwrites custom trigger process names you set manually on individual profiles.

---

## [0.1.0] - 2026-02-18

Initial public release.

### Features
- System-tray app — runs silently in the background, opens on demand.
- Monitors iRacing and launches configured apps automatically when it starts.
- Optional auto-stop — apps can be closed when iRacing exits.
- Multiple profiles — each with its own app list and trigger settings.
- Wait-for dependency — delay an app's launch until another process is running.
- Start minimized option per app.
- Pause / resume monitoring from the tray or UI.
- Manual start / stop per app from the UI.
- Test-launch button — launch an app outside of an iRacing session.
- Drag-and-drop app reordering.
- Undo for accidental app deletion.
- Profile color labels and enable / disable toggle.
- Import / export config as JSON.
- Windows autostart on login.
- Race button — starts iRacing via Steam or a custom exe path.
- Session history and activity log.
- Dark and iRacing themes.
