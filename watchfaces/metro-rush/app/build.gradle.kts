plugins {
    id("com.android.application")
}

android {
    namespace = "io.github.ingdas.metrorush"
    compileSdk = 34

    defaultConfig {
        applicationId = "io.github.ingdas.metrorush"
        // Watch Face Format v1 needs Wear OS 4 (API 33) or newer.
        minSdk = 33
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    signingConfigs {
        // Sideload-only key, committed on purpose: every build (local or CI) gets the same
        // signature, so a new APK installs over the previous one. Not for Play Store use.
        create("sideload") {
            storeFile = rootProject.file("signing/sideload.jks")
            storePassword = "metro-rush-sideload"
            keyAlias = "sideload"
            keyPassword = "metro-rush-sideload"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("sideload")
        }
    }
}
