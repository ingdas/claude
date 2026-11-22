package io.github.ingdas.watchfaces

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.ParcelFileDescriptor
import androidx.wear.watchfacepush.WatchFacePushManagerFactory
import java.io.File

/** Installs or updates a watch face APK with Watch Face Push and makes it the active face. */
object PushInstaller {
    const val SET_ACTIVE_PERMISSION = "com.google.wear.permission.SET_PUSHED_WATCH_FACE_AS_ACTIVE"

    fun isSupported() = Build.VERSION.SDK_INT >= 36 // Watch Face Push needs Wear OS 6

    /** Returns a human-readable result (shown on the phone and on the watch). */
    suspend fun install(context: Context, apk: File, token: String): String {
        if (!isSupported()) return "This watch runs API ${Build.VERSION.SDK_INT}; Watch Face Push needs Wear OS 6."
        val info = context.packageManager.getPackageArchiveInfo(apk.path, PackageManager.PackageInfoFlags.of(0))
            ?: return "The received file is not a valid APK."
        val pkg = info.packageName
        val newVersion = info.longVersionCode
        val manager = WatchFacePushManagerFactory.createWatchFacePushManager(context)

        val before = manager.listWatchFaces()
        val existing = before.installedWatchFaceDetails.firstOrNull { it.packageName == pkg }
        val action: String
        when {
            existing != null && existing.versionCode >= newVersion -> action = "already installed"
            existing != null -> {
                open(apk).use { manager.updateWatchFace(existing.slotId, it, token) }
                action = "updated"
            }
            before.remainingSlotCount > 0 -> {
                open(apk).use { manager.addWatchFace(it, token) }
                action = "installed"
            }
            else -> {
                // All slots taken by other faces: replace the first one.
                val slot = before.installedWatchFaceDetails.first().slotId
                try {
                    open(apk).use { manager.updateWatchFace(slot, it, token) }
                } catch (e: Exception) {
                    manager.removeWatchFace(slot)
                    open(apk).use { manager.addWatchFace(it, token) }
                }
                action = "installed (replaced the previous face)"
            }
        }

        val slot = manager.listWatchFaces().installedWatchFaceDetails.firstOrNull { it.packageName == pkg }?.slotId
            ?: return "Face $action, but it isn't listed afterwards."
        if (manager.isWatchFaceActive(pkg)) return "Face $action and active ✔"
        if (context.checkSelfPermission(SET_ACTIVE_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            return "Face $action ✔. To switch to it automatically, open “Watch Faces” on the watch once " +
                "and allow it to set the watch face — or pick it yourself: touch and hold the watch face."
        }
        return try {
            manager.setWatchFaceAsActive(slot)
            "Face $action and set as your watch face ✔"
        } catch (e: Exception) {
            "Face $action ✔, but the watch didn't let it become active automatically (${e.message}). " +
                "Touch and hold the watch face to pick it."
        }
    }

    private fun open(apk: File) = ParcelFileDescriptor.open(apk, ParcelFileDescriptor.MODE_READ_ONLY)
}
