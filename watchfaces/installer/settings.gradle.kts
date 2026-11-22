pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven("https://jitpack.io") // libadb-android and its SPAKE2 dependency
    }
}

rootProject.name = "watch-face-installer"
include(":app")  // phone app
include(":wear") // watch companion (Watch Face Push marketplace)
include(":tokengen") // runs the Watch Face Push validator (separate JVM)
