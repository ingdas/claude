// Puts Google's Watch Face Push validator on the build-script classpath, so :wear can generate
// the validation tokens that the Watch Face Push API requires for every face it installs.
plugins {
    `kotlin-dsl`
}

repositories {
    google()
    mavenCentral()
    // Required by the validator's dependencies (per the Watch Face Push docs).
    maven {
        url = uri("https://jitpack.io")
        content { includeGroup("com.github.xgouchet") }
    }
    gradlePluginPortal()
}

dependencies {
    implementation("com.google.android.wearable.watchface.validator:validator-push:1.0.0-alpha10")
}
