# Watch Face Installer (phone app)

An Android phone app (Android 11+) that installs the bundled **Metro Rush** and
**Hatched Hour** watch faces onto a Galaxy Watch over Wi-Fi. No computer needed.
Download [`apk/watch-face-installer.apk`](apk/watch-face-installer.apk) on the phone and open it
to install.

It uses the watch's own **Wireless debugging** (the same mechanism as `adb pair` and
`adb install`), implemented with [libadb-android](https://github.com/MuntashirAkon/libadb-android)
under its Apache-2.0 license option.

## Use it

1. **Watch:** go to *Settings → About watch → Software information* and tap **Software version**
   5 times.
2. **Watch:** go to *Settings → Developer options* and turn on **ADB debugging** and
   **Wireless debugging**. The phone and watch must be on the same Wi-Fi. To make sure the watch
   is really on Wi-Fi, set *Settings → Connections → Wi-Fi* to **Always on**.
3. **Watch:** tap **Wireless debugging → Pair new device**. In the app, enter the IP address,
   pairing port and pairing code, then tap **Pair**. You only need to pair once.
4. **Watch:** go back to the Wireless debugging screen. In the app, enter the port shown next to
   the IP address and tap **Connect**.
5. In the app, tap **Install Metro Rush** and/or **Install Hatched Hour**.
6. **Watch:** touch and hold the watch face, then tap **+ Add watch face** and pick the face.
   Under **Customise**, set the two buttons to *App shortcut → Spotify / Google Wallet*.

Turn Wireless debugging off again when you're done.

## Notes

- The installer is signed with the same throwaway sideload key as the faces (`../signing/`).
- CI rebuilds it after the faces, so it always bundles the latest watch face APKs.
- It hasn't been tested against a physical watch yet. If a step fails, the app shows the
  error text; send it over.
