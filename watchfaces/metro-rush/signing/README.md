`sideload.jks` is a throwaway signing key for sideloading Metro Rush with `adb install`.
Its password is in `app/build.gradle.kts` on purpose, so every build gets the same signature
and new APKs install over old ones. It protects nothing; don't use it for anything else.
