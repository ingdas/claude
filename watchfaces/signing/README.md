Throwaway signing keys for sideloading. Their passwords are in the Gradle files on purpose, so
every build (local or CI) gets the same signature and new APKs install over old ones. They
protect nothing; don't use them for anything else.

- `sideload.jks`: the apps (phone installer and watch companion). The phone app and watch app
  must share a key for Wear OS Data Layer messaging between them.
- `watchface.jks`: the watch faces. Watch Face Push requires faces to be signed with a
  different key than the marketplace app that installs them.
