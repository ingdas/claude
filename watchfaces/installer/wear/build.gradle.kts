import com.google.android.wearable.watchface.validator.client.DwfValidatorFactory

plugins {
    id("com.android.application")
}

// The watch companion is a Watch Face Push "marketplace" app. It shares its package name and
// signing key with the phone app, which the Wear OS Data Layer needs to connect the two.
val marketplacePackage = "io.github.ingdas.watchfaces"

// Faces this marketplace can install: project folder -> short id (the package suffix).
val faces = mapOf("metro-rush" to "metrorush", "hatched-hour" to "hatchedhour")
fun pushApk(dir: String) = rootProject.file("../$dir/apk/$dir-push.apk")

android {
    namespace = "io.github.ingdas.watchfaces"
    compileSdk = 36

    defaultConfig {
        applicationId = marketplacePackage
        minSdk = 33 // the Push API itself only works on Wear OS 6 (API 36); checked at runtime
        targetSdk = 36
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "1.0"
    }

    signingConfigs {
        create("sideload") {
            storeFile = rootProject.file("../signing/sideload.jks")
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

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation("androidx.wear.watchfacepush:watchfacepush:1.0.0")
    implementation("com.google.android.gms:play-services-wearable:19.0.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
}

// ---- Validation tokens -------------------------------------------------------------------
// Watch Face Push only accepts a face together with a token from Google's official validator,
// generated for this marketplace's package name. The tokens are shared with the phone app,
// which sends each face + token to the watch over Bluetooth.
val tokenDir = layout.buildDirectory.dir("generated/pushTokens")
val generatePushTokens by tasks.registering {
    val apks = faces.keys.map { pushApk(it) }
    inputs.files(apks)
    outputs.dir(tokenDir)
    doLast {
        val validator = DwfValidatorFactory.create()
        faces.forEach { (dir, id) ->
            val apk = pushApk(dir)
            if (!apk.exists()) throw GradleException("Missing $apk: build the $dir push flavor first")
            val result = validator.validate(apk, marketplacePackage)
            val failures = result.failures()
            if (failures.isNotEmpty()) {
                throw GradleException("$dir failed Watch Face Push validation:\n" +
                    failures.joinToString("\n") { "  - $it" })
            }
            val out = tokenDir.get().file("${id}_token.txt").asFile
            out.parentFile.mkdirs()
            out.writeText(result.validationToken())
        }
    }
}

// The default watch face (required for a marketplace app) is Metro Rush: it's bundled as
// assets/default_watchface.apk and its token goes into the manifest via @string/default_wf_token.
val defaultAssets = layout.buildDirectory.dir("generated/defaultWatchFace/assets")
val defaultRes = layout.buildDirectory.dir("generated/defaultWatchFace/res")
val prepareDefaultWatchFace by tasks.registering {
    dependsOn(generatePushTokens)
    inputs.dir(tokenDir)
    inputs.file(pushApk("metro-rush"))
    outputs.dirs(defaultAssets, defaultRes)
    doLast {
        val assets = defaultAssets.get().asFile.apply { mkdirs() }
        pushApk("metro-rush").copyTo(assets.resolve("default_watchface.apk"), overwrite = true)
        val token = tokenDir.get().file("metrorush_token.txt").asFile.readText().trim()
        val values = defaultRes.get().asFile.resolve("values").apply { mkdirs() }
        values.resolve("default_wf_token.xml").writeText(
            "<resources>\n    <string name=\"default_wf_token\" translatable=\"false\">$token</string>\n</resources>\n"
        )
    }
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addStaticSourceDirectory(defaultAssets.get().asFile.absolutePath)
        variant.sources.res?.addStaticSourceDirectory(defaultRes.get().asFile.absolutePath)
    }
}

tasks.matching { it.name.startsWith("pre") && it.name.endsWith("Build") }.configureEach { dependsOn(prepareDefaultWatchFace) }
