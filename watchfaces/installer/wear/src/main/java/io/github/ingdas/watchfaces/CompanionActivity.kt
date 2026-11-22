package io.github.ingdas.watchfaces

import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.wear.watchfacepush.WatchFacePushManagerFactory
import kotlinx.coroutines.runBlocking

/**
 * The watch-side screen. Its main job is the one-time permission that lets the companion switch
 * to a face as soon as it arrives from the phone; it also shows what is installed.
 */
class CompanionActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var allow: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pad = (resources.displayMetrics.widthPixels * 0.12).toInt()
        status = TextView(this).apply { gravity = Gravity.CENTER; textSize = 14f }
        allow = Button(this).apply {
            text = "Allow setting the watch face"
            setOnClickListener { requestPermissions(arrayOf(PushInstaller.SET_ACTIVE_PERMISSION), 1) }
        }
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(pad, pad, pad, pad)
            addView(TextView(context).apply {
                text = "Watch Faces"; textSize = 18f; gravity = Gravity.CENTER
            })
            addView(status)
            addView(allow)
        }
        setContentView(ScrollView(this).apply { addView(column) })
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<String>, grantResults: IntArray) {
        refresh()
    }

    private fun refresh() {
        val granted = checkSelfPermission(PushInstaller.SET_ACTIVE_PERMISSION) == PackageManager.PERMISSION_GRANTED
        allow.visibility = if (granted) View.GONE else View.VISIBLE
        Thread {
            val text = buildString {
                if (!PushInstaller.isSupported()) {
                    append("This watch needs Wear OS 6 (One UI 8 Watch) for Watch Face Push.")
                    return@buildString
                }
                append("Ready. Send faces from the phone app over Bluetooth.\n\n")
                try {
                    val manager = WatchFacePushManagerFactory.createWatchFacePushManager(this@CompanionActivity)
                    val faces = runBlocking { manager.listWatchFaces() }
                    faces.installedWatchFaceDetails.forEach {
                        val active = runBlocking { manager.isWatchFaceActive(it.packageName) }
                        append("• ${it.packageName.substringAfterLast('.')} v${it.versionCode}")
                        append(if (active) " (active)\n" else "\n")
                    }
                    append("Free slots: ${faces.remainingSlotCount}\n")
                } catch (e: Exception) {
                    append("Couldn't list faces: ${e.message}\n")
                }
                LastResult.load(this@CompanionActivity)?.let { append("\nLast: $it") }
                if (!granted) append("\n\nTap below once so new faces become active automatically.")
            }
            runOnUiThread { status.text = text }
        }.start()
    }
}

/** The result of the last install, so the watch screen can show it too. */
object LastResult {
    fun save(context: Context, text: String) =
        context.getSharedPreferences("push", Context.MODE_PRIVATE).edit().putString("last", text).apply()

    fun load(context: Context): String? =
        context.getSharedPreferences("push", Context.MODE_PRIVATE).getString("last", null)
}
