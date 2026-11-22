plugins {
    id("com.android.application")
}

android {
    namespace = "io.github.ingdas.watchinstaller"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.ingdas.watchinstaller"
        // Wireless-debugging pairing (TLS + SPAKE2) needs Android 11+.
        minSdk = 30
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }

    signingConfigs {
        // Same throwaway sideload key as the watch faces (see ../signing/README.md).
        create("sideload") {
            storeFile = rootProject.file("../signing/sideload.jks")
            storePassword = "metro-rush-sideload"
            keyAlias = "sideload"
            keyPassword = "metro-rush-sideload"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false // libadb uses reflection on Conscrypt
            signingConfig = signingConfigs.getByName("sideload")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("generated/watchFaceApks"))
}

// Bundle the watch face APKs (built by their own projects) as assets.
val copyWatchFaceApks by tasks.registering(Copy::class) {
    from(rootProject.file("../metro-rush/apk/metro-rush.apk"))
    from(rootProject.file("../hatched-hour/apk/hatched-hour.apk"))
    into(layout.buildDirectory.dir("generated/watchFaceApks"))
}
tasks.named("preBuild") { dependsOn(copyWatchFaceApks) }

dependencies {
    implementation("com.github.MuntashirAkon:libadb-android:3.1.1")
    implementation("org.conscrypt:conscrypt-android:2.5.3")      // TLS for remote pairing/connect
    implementation("org.bouncycastle:bcpkix-jdk15to18:1.81")     // self-signed ADB certificate
}
