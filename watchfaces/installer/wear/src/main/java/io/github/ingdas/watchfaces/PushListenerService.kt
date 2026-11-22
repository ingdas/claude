package io.github.ingdas.watchfaces

import android.util.Log
import com.google.android.gms.tasks.Tasks
import com.google.android.gms.wearable.ChannelClient
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService
import kotlinx.coroutines.runBlocking
import java.io.DataInputStream
import java.io.File

/**
 * Receives a watch face from the phone over the Data Layer (Bluetooth). The phone opens a channel
 * on "/push/<face>" and writes: [int tokenLength][token UTF-8 bytes][APK bytes until end of stream].
 * The result is sent back to the phone as a message on "/push-result".
 */
class PushListenerService : WearableListenerService() {

    override fun onChannelOpened(channel: ChannelClient.Channel) {
        if (!channel.path.startsWith("/push/")) return
        val channels = Wearable.getChannelClient(this)
        val result = try {
            val apk = File(cacheDir, "incoming.apk")
            val token: String
            DataInputStream(Tasks.await(channels.getInputStream(channel))).use { input ->
                val length = input.readInt()
                require(length in 1..65536) { "bad token length $length" }
                val bytes = ByteArray(length).also { input.readFully(it) }
                token = String(bytes, Charsets.UTF_8)
                apk.outputStream().use { input.copyTo(it) }
            }
            runBlocking { PushInstaller.install(this@PushListenerService, apk, token) }
        } catch (e: Exception) {
            Log.e(TAG, "Install failed", e)
            "Install on the watch failed: ${e.javaClass.simpleName}: ${e.message}"
        } finally {
            channels.close(channel)
        }
        Log.i(TAG, result)
        LastResult.save(this, result)
        Wearable.getMessageClient(this).sendMessage(channel.nodeId, "/push-result", result.toByteArray())
    }

    companion object {
        private const val TAG = "PushListenerService"
    }
}
