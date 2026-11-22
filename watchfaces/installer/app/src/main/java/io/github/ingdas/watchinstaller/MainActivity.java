package io.github.ingdas.watchinstaller;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import com.google.android.gms.tasks.Tasks;
import com.google.android.gms.wearable.CapabilityClient;
import com.google.android.gms.wearable.CapabilityInfo;
import com.google.android.gms.wearable.ChannelClient;
import com.google.android.gms.wearable.MessageClient;
import com.google.android.gms.wearable.MessageEvent;
import com.google.android.gms.wearable.Node;
import com.google.android.gms.wearable.Wearable;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import io.github.muntashirakon.adb.AdbPairingRequiredException;
import io.github.muntashirakon.adb.AdbStream;

/**
 * Everyday path: sends a bundled watch face (+ its Watch Face Push validation token) over the
 * Bluetooth Data Layer to the "Watch Faces" companion on the watch, which installs it.
 * One-time setup: pairs with the watch over Wireless debugging and installs that companion
 * via {@code cmd package install}. Everything I/O-related runs on a background thread.
 */
public class MainActivity extends Activity implements MessageClient.OnMessageReceivedListener {
    private static final int CHUNK = 16 * 1024; // stay well below adbd's max packet payload
    private static final String CAPABILITY = "watchface_push_companion";

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private EditText host, pairPort, pairCode, connectPort;
    private Button installCompanion;
    private TextView log;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        prefs = getSharedPreferences("watch", MODE_PRIVATE);
        host = findViewById(R.id.host);
        pairPort = findViewById(R.id.pairPort);
        pairCode = findViewById(R.id.pairCode);
        connectPort = findViewById(R.id.connectPort);
        installCompanion = findViewById(R.id.installCompanion);
        log = findViewById(R.id.log);
        host.setText(prefs.getString("host", ""));
        connectPort.setText(prefs.getString("connectPort", ""));

        findViewById(R.id.pair).setOnClickListener(v -> pair());
        findViewById(R.id.connect).setOnClickListener(v -> connect());
        installCompanion.setOnClickListener(v -> install("watch-companion.apk", "The Watch Faces companion"));
        findViewById(R.id.sendMetro).setOnClickListener(v -> send("metrorush", "Metro Rush"));
        findViewById(R.id.sendHatched).setOnClickListener(v -> send("hatchedhour", "Hatched Hour"));
    }

    @Override
    protected void onResume() {
        super.onResume();
        Wearable.getMessageClient(this).addListener(this);
    }

    @Override
    protected void onPause() {
        super.onPause();
        Wearable.getMessageClient(this).removeListener(this);
    }

    /** The companion replies on "/push-result" once it has installed (or failed to install) a face. */
    @Override
    public void onMessageReceived(MessageEvent event) {
        if ("/push-result".equals(event.getPath())) {
            say("Watch: " + new String(event.getData(), StandardCharsets.UTF_8));
        }
    }

    /** Sends [int tokenLength][token][APK bytes] on channel "/push/<id>" to the companion. */
    private void send(String id, String label) {
        say("Looking for the watch …");
        worker.execute(() -> {
            try {
                CapabilityInfo info = Tasks.await(Wearable.getCapabilityClient(this)
                        .getCapability(CAPABILITY, CapabilityClient.FILTER_REACHABLE));
                Node watch = null;
                for (Node node : info.getNodes()) {
                    if (watch == null || node.isNearby()) watch = node;
                }
                if (watch == null) {
                    say("No watch with the Watch Faces companion is connected.\nIf you haven't yet,"
                            + " do the one-time setup below. Otherwise check the watch is connected"
                            + " in Galaxy Wearable.");
                    return;
                }
                byte[] apk = readAsset(id + ".apk");
                byte[] token = new String(readAsset(id + "_token.txt"), StandardCharsets.UTF_8)
                        .trim().getBytes(StandardCharsets.UTF_8);
                say("Sending " + label + " to " + watch.getDisplayName() + " over Bluetooth ("
                        + apk.length / 1024 + " KB) …");
                ChannelClient channels = Wearable.getChannelClient(this);
                ChannelClient.Channel channel = Tasks.await(channels.openChannel(watch.getId(), "/push/" + id));
                try (DataOutputStream out = new DataOutputStream(Tasks.await(channels.getOutputStream(channel)))) {
                    out.writeInt(token.length);
                    out.write(token);
                    for (int off = 0; off < apk.length; off += CHUNK) {
                        out.write(apk, off, Math.min(CHUNK, apk.length - off));
                    }
                    out.flush();
                }
                say("Sent. Waiting for the watch to install it …");
            } catch (Throwable t) {
                say("Sending " + label + " failed: " + describe(t));
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (isFinishing()) {
            worker.execute(() -> {
                try {
                    AdbManager.get(this).disconnect();
                } catch (Exception ignored) {
                }
            });
        }
        worker.shutdown();
    }

    private void pair() {
        String h = text(host), port = text(pairPort), code = text(pairCode);
        if (h.isEmpty() || port.isEmpty() || code.isEmpty()) {
            say("Fill in the watch IP, pairing port and pairing code first.");
            return;
        }
        prefs.edit().putString("host", h).apply();
        say("Pairing with " + h + ":" + port + " …");
        worker.execute(() -> {
            try {
                AdbManager.get(this).pair(h, Integer.parseInt(port), code);
                prefs.edit().putBoolean("paired", true).apply();
                say("Paired ✔ Now enter the port shown next to the IP address on the Wireless debugging"
                        + " screen and tap Connect.");
            } catch (Throwable t) {
                say("Pairing failed: " + describe(t)
                        + "\nCheck the code hasn't expired (the pairing dialog must stay open on the watch).");
            }
        });
    }

    private void connect() {
        String h = text(host), port = text(connectPort);
        if (h.isEmpty() || port.isEmpty()) {
            say("Fill in the watch IP and the connection port first.");
            return;
        }
        prefs.edit().putString("host", h).putString("connectPort", port).apply();
        say("Connecting to " + h + ":" + port + " …");
        worker.execute(() -> {
            try {
                AdbManager adb = AdbManager.get(this);
                adb.setTimeout(15, TimeUnit.SECONDS);
                if (adb.isConnected()) {
                    adb.disconnect();
                }
                // connect() returns false (instead of throwing) when the watch doesn't answer in time.
                if (!adb.connect(h, Integer.parseInt(port)) && !adb.isConnected()) {
                    say("The watch didn't answer within 15 s."
                            + (prefs.getBoolean("paired", false) ? "" : "\nThis phone isn't paired yet:"
                                + " on the watch tap Wireless debugging › Pair new device, enter that"
                                + " port and 6-digit code above, tap Pair, then Connect again.")
                            + "\nAlso check the port: it's the one next to the IP on the Wireless"
                            + " debugging screen, and it changes whenever Wireless debugging is turned"
                            + " off and on.");
                    adb.disconnect();
                    return;
                }
                String sdk = shell(adb, "getprop ro.build.version.sdk").trim();
                String model = shell(adb, "getprop ro.product.model").trim();
                say("Connected to " + model + " (API " + sdk + ").");
                if (!sdk.isEmpty() && Integer.parseInt(sdk) < 33) {
                    say("This watch runs API " + sdk + ". The watch faces need Wear OS 4 (API 33) or newer —"
                            + " update the watch software first.");
                }
                runOnUiThread(() -> installCompanion.setEnabled(true));
            } catch (AdbPairingRequiredException e) {
                say("The watch doesn't know this phone yet: do step 1 (Pair) first.");
            } catch (Throwable t) {
                say("Connect failed: " + describe(t)
                        + "\nUse the port next to the IP on the Wireless debugging screen (not the pairing port).");
            }
        });
    }

    private void install(String asset, String label) {
        say("Installing " + label + " …");
        worker.execute(() -> {
            try {
                byte[] apk = readAsset(asset);
                AdbManager adb = AdbManager.get(this);
                AdbStream stream = adb.openStream("exec:cmd package install -r -S " + apk.length);
                try (OutputStream out = stream.openOutputStream()) {
                    for (int off = 0; off < apk.length; off += CHUNK) {
                        out.write(apk, off, Math.min(CHUNK, apk.length - off));
                    }
                    out.flush();
                    String result = readAll(stream.openInputStream()).trim();
                    if (result.contains("Success")) {
                        say(label + " is installed ✔ It comes with Metro Rush built in.\nOn the watch:"
                                + " open the “Watch Faces” app once and tap “Allow setting the watch face”."
                                + "\nFrom now on use the Bluetooth buttons above; you can turn Wireless"
                                + " debugging off.");
                    } else {
                        say(label + " install failed: " + result);
                    }
                }
                stream.close();
            } catch (Throwable t) {
                say(label + " install failed: " + describe(t) + "\nTry Connect again, then install.");
            }
        });
    }

    private static String shell(AdbManager adb, String command) throws Exception {
        AdbStream stream = adb.openStream("exec:" + command);
        try {
            return readAll(stream.openInputStream());
        } finally {
            stream.close();
        }
    }

    private static String readAll(InputStream in) {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        byte[] b = new byte[4096];
        try {
            int n;
            while ((n = in.read(b)) >= 0) {
                buf.write(b, 0, n);
            }
        } catch (IOException endOfStream) {
            // libadb may report the peer closing the stream as "Stream closed." instead of -1.
        }
        return new String(buf.toByteArray(), StandardCharsets.UTF_8);
    }

    private byte[] readAsset(String name) throws Exception {
        try (InputStream in = getAssets().open(name)) {
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            byte[] b = new byte[8192];
            int n;
            while ((n = in.read(b)) > 0) {
                buf.write(b, 0, n);
            }
            return buf.toByteArray();
        }
    }

    private static String describe(Throwable t) {
        Throwable root = t;
        while (root.getCause() != null && root.getCause() != root) {
            root = root.getCause();
        }
        String msg = root.getMessage();
        return root.getClass().getSimpleName() + (msg != null ? ": " + msg : "");
    }

    private static String text(EditText e) {
        return e.getText().toString().trim();
    }

    private void say(String message) {
        runOnUiThread(() -> log.append(message + "\n\n"));
    }
}
