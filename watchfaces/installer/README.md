# Watch Faces: phone app + watch companion

Sends **Metro Rush** and **Hatched Hour** to a Galaxy Watch over the normal Bluetooth connection,
using Wear OS 6's **Watch Face Push** API, the same mechanism watch face marketplace apps use.
The watch needs **One UI 8 Watch / Wear OS 6**.

| APK | Install on | What it does |
| --- | --- | --- |
| [`apk/watch-faces-phone.apk`](apk/watch-faces-phone.apk) | **phone** (Android 11+) | Sends faces over Bluetooth; one-time companion setup |
| [`apk/watch-faces-companion.apk`](apk/watch-faces-companion.apk) | **watch**, once | Receives faces from the phone and installs them. The phone app installs it for you. |

## One-time setup (about two minutes)

The watch only accepts a new app over Bluetooth through Galaxy Wearable or the Play Store, and
neither can be used for a sideloaded app. So the companion goes on once over Wi-Fi debugging.
No internet is needed:

1. Turn on your **phone's hotspot** and connect the watch to it. Using the same Wi-Fi also works.
2. On the watch, go to *Settings → About watch → Software information* and tap
   **Software version** 5 times.
3. Go to *Settings → Developer options* and turn on **ADB debugging** and **Wireless debugging**.
4. In the phone app, under *One-time setup*, enter what **Wireless debugging → Pair new device**
   shows and tap **Pair**. Then enter the connection port and tap **Connect**.
5. Tap **Install companion**. Metro Rush comes built in as the companion's default face.
6. On the watch, open **Watch Faces** once and tap **Allow setting the watch face**.
7. Turn Wireless debugging off.

## Every time after that

Tap **Send Metro Rush** or **Send Hatched Hour** in the phone app. The face travels over
Bluetooth, and the companion installs it (or updates it, if a newer build) and makes it your
watch face. The app shows the watch's reply.

To get new versions of the faces, install the newer `watch-faces-phone.apk` on the phone. It
bundles the latest faces. Then tap **Send** again.

## How it works

- **The watch companion (`wear/`)** is a Watch Face Push "marketplace" app. A Data Layer
  `WearableListenerService` receives `[token length][token][APK]` on channel `/push/<face>`. It
  then calls `WatchFacePushManager.addWatchFace` / `updateWatchFace` and `setWatchFaceAsActive`,
  and replies on `/push-result`.
- **The phone app (`app/`)** finds the watch through the `watchface_push_companion` capability
  and streams the face over a `ChannelClient` channel. Both apps share the package
  `io.github.ingdas.watchfaces` and a signing key, which the Data Layer requires.
- **Faces** are built in a `push` flavor named
  `io.github.ingdas.watchfaces.watchfacepush.<face>`, a naming rule the API enforces. They're
  signed with a separate key (`../signing/watchface.jks`), as the docs require. At build time,
  Google's `validator-push` checks each one and produces the validation token the API demands.
- **The one-time ADB install** uses [libadb-android](https://github.com/MuntashirAkon/libadb-android)
  (Apache-2.0 option) for Wireless-debugging pairing, then `cmd package install`.

Not yet tested on a physical watch. If something fails, both apps show the error; send it over.
