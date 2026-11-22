package io.github.ingdas.watchinstaller;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import java.io.ByteArrayOutputStream;
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
 * Pairs with the watch over Wireless debugging, connects, and streams a bundled watch face APK
 * into {@code cmd package install}. Everything network-related runs on a background thread.
 */
public class MainActivity extends Activity {
    private static final int CHUNK = 16 * 1024; // stay well below adbd's max packet payload

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private EditText host, pairPort, pairCode, connectPort;
    private Button installMetro, installHatched;
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
        installMetro = findViewById(R.id.installMetro);
        installHatched = findViewById(R.id.installHatched);
        log = findViewById(R.id.log);
        host.setText(prefs.getString("host", ""));
        connectPort.setText(prefs.getString("connectPort", ""));

        findViewById(R.id.pair).setOnClickListener(v -> pair());
        findViewById(R.id.connect).setOnClickListener(v -> connect());
        installMetro.setOnClickListener(v -> install("metro-rush.apk", "Metro Rush"));
        installHatched.setOnClickListener(v -> install("hatched-hour.apk", "Hatched Hour"));
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
                say("Paired. Now enter the connection port and tap Connect.");
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
                adb.connect(h, Integer.parseInt(port));
                String sdk = shell(adb, "getprop ro.build.version.sdk").trim();
                String model = shell(adb, "getprop ro.product.model").trim();
                say("Connected to " + model + " (API " + sdk + ").");
                if (!sdk.isEmpty() && Integer.parseInt(sdk) < 33) {
                    say("This watch runs API " + sdk + ". The watch faces need Wear OS 4 (API 33) or newer —"
                            + " update the watch software first.");
                }
                runOnUiThread(() -> {
                    installMetro.setEnabled(true);
                    installHatched.setEnabled(true);
                });
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
                        say(label + " installed ✔\nOn the watch: touch and hold the watch face › swipe to"
                                + " “+ Add watch face” › pick " + label + ".\nThen Customise › set the two"
                                + " shortcut buttons to App shortcut › Spotify / Google Wallet.");
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
