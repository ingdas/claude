// Runs Google's Watch Face Push validator in its own JVM (see :wear's generatePushTokens).
// It must not share a classpath with the Android Gradle Plugin: the validator bundles an older
// copy of AGP's resource-format classes, which would break resource merging.
plugins {
    `java-library`
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

dependencies {
    implementation("com.google.android.wearable.watchface.validator:validator-push:1.0.0-alpha09")
}
