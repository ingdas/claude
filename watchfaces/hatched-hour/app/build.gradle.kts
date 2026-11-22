plugins {
    id("com.android.application")
}

android {
    namespace = "io.github.ingdas.hatchedhour"
    compileSdk = 34

    buildFeatures {
        buildConfig = false
    }

    defaultConfig {
        applicationId = "io.github.ingdas.hatchedhour"
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
            storeFile = rootProject.file("../signing/sideload.jks")
            storePassword = "metro-rush-sideload"
            keyAlias = "sideload"
            keyPassword = "metro-rush-sideload"
        }
    }

    buildTypes {
        release {
            // No code in a Watch Face Format APK: R8 strips the generated R classes so the
            // APK ships without a classes.dex.
            isMinifyEnabled = true
            isShrinkResources = false
            signingConfig = signingConfigs.getByName("sideload")
        }
    }
}
