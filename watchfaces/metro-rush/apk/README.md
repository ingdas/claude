# Metro Rush: installable APK

`metro-rush.apk` is the Metro Rush watch face for the Galaxy Watch 4 (Watch Face Format v1,
resource-only, Wear OS 4+). It's built by CI from the source in PR #2, at commit `ffb6b16`,
and passed Google's official WFF validator.

Install over wireless ADB:

1. On the watch: *Settings → About watch → Software information*, tap **Software version** 5 times.
2. *Settings → Developer options*: turn on **ADB debugging** and **Wireless debugging**, then
   tap **Pair new device**.
3. On a computer with platform-tools:
   ```sh
   adb pair <ip>:<pairing-port>     # enter the pairing code
   adb connect <ip>:<port>
   adb install -r metro-rush.apk
   ```
4. Long-press the watch face, tap **+ Add watch face**, and pick **Metro Rush**. Under
   **Customise**, set the palette and choose *App shortcut → Spotify / Google Wallet* for the
   8 and 4 o'clock stations.

It's signed with the sideload key from PR #2, so later builds from that PR install over this one.
