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

    buildTypes {
        release {
            isMinifyEnabled = false
            // Sideload-only: sign release builds with the debug key so `adb install` just works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}
