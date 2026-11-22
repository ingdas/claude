plugins {
    id("com.android.application")
}

android {
    namespace = "io.github.ingdas.watchinstaller"
    compileSdk = 36

    defaultConfig {
        // Same package name and signing key as the watch companion (:wear): the Wear OS Data
        // Layer only connects a phone app to the watch app with the same package and signature.
        applicationId = "io.github.ingdas.watchfaces"
        // Wireless-debugging pairing (TLS + SPAKE2) needs Android 11+.
        minSdk = 30
        targetSdk = 36
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "2.0"
    }

    signingConfigs {
        // Same throwaway sideload key as the watch companion (see ../signing/README.md).
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
}

// Bundled assets:
//  - watch-companion.apk: installed once on the watch over Wi-Fi debugging
//  - <face>.apk + <face>_token.txt: Watch Face Push builds, sent to the companion over Bluetooth
val bundled = layout.buildDirectory.dir("generated/bundledApks")
val copyBundledApks by tasks.registering(Copy::class) {
    dependsOn(":wear:assembleRelease", ":wear:generatePushTokens")
    from(project(":wear").layout.buildDirectory.file("outputs/apk/release/wear-release.apk")) {
        rename { "watch-companion.apk" }
    }
    from(project(":wear").layout.buildDirectory.dir("generated/pushTokens"))
    from(rootProject.file("../metro-rush/apk/metro-rush-push.apk")) { rename { "metrorush.apk" } }
    from(rootProject.file("../hatched-hour/apk/hatched-hour-push.apk")) { rename { "hatchedhour.apk" } }
    into(bundled)
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addStaticSourceDirectory(bundled.get().asFile.absolutePath)
    }
}

tasks.matching { it.name.startsWith("pre") && it.name.endsWith("Build") }.configureEach { dependsOn(copyBundledApks) }

dependencies {
    implementation("com.github.MuntashirAkon:libadb-android:3.1.1")
    implementation("org.conscrypt:conscrypt-android:2.5.3")          // TLS for remote pairing/connect
    implementation("org.bouncycastle:bcpkix-jdk15to18:1.81")         // self-signed ADB certificate
    implementation("com.google.android.gms:play-services-wearable:19.0.0") // Bluetooth Data Layer
}
