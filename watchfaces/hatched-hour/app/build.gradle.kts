plugins {
    id("com.android.application")
}

// Marketplace (Watch Face Push) app that may install the "push" flavor of this face.
val marketplacePackage = "io.github.ingdas.watchfaces"

android {
    namespace = "io.github.ingdas.hatchedhour"
    compileSdk = 34

    buildFeatures {
        buildConfig = false
    }

    defaultConfig {
        // Watch Face Format v1 needs Wear OS 4 (API 33) or newer.
        minSdk = 33
        targetSdk = 34
        // CI run number, so every CI build can update the face that's already on the watch.
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "1.0"
    }

    flavorDimensions += "distribution"
    productFlavors {
        // Installed directly with `adb install`.
        create("standalone") {
            dimension = "distribution"
            applicationId = "io.github.ingdas.hatchedhour"
        }
        // Installed over Bluetooth by the companion app via Watch Face Push, which requires
        // the package name "<marketplace package>.watchfacepush.<face>".
        create("push") {
            dimension = "distribution"
            applicationId = "$marketplacePackage.watchfacepush.hatchedhour"
        }
    }

    signingConfigs {
        // Throwaway key for the faces, committed on purpose (see ../signing/README.md). Watch
        // Face Push requires faces to be signed with a different key than the marketplace app.
        create("watchface") {
            storeFile = rootProject.file("../signing/watchface.jks")
            storePassword = "watchface-sideload"
            keyAlias = "watchface"
            keyPassword = "watchface-sideload"
        }
    }

    buildTypes {
        release {
            // No code in a Watch Face Format APK: R8 strips the generated R classes so the
            // APK ships without a classes.dex.
            isMinifyEnabled = true
            isShrinkResources = false
            signingConfig = signingConfigs.getByName("watchface")
        }
    }
}
