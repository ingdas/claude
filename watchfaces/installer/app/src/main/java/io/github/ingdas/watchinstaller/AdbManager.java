package io.github.ingdas.watchinstaller;

import android.content.Context;

import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.cert.X509v3CertificateBuilder;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.math.BigInteger;
import java.nio.file.Files;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.Date;

import io.github.muntashirakon.adb.AbsAdbConnectionManager;

/**
 * ADB client identity for this app. The RSA key and self-signed certificate are generated once and
 * stored in the app's private files, so the watch only needs to be paired once.
 */
final class AdbManager extends AbsAdbConnectionManager {
    private static AdbManager instance;

    private final PrivateKey privateKey;
    private final Certificate certificate;

    static synchronized AdbManager get(Context context) throws Exception {
        if (instance == null) {
            instance = new AdbManager(context.getApplicationContext());
        }
        return instance;
    }

    private AdbManager(Context context) throws Exception {
        // API level of the remote adbd. The watch faces need Wear OS 4 (API 33) or newer.
        setApi(33);
        File keyFile = new File(context.getFilesDir(), "adb.key");
        File certFile = new File(context.getFilesDir(), "adb.crt");
        if (keyFile.exists() && certFile.exists()) {
            privateKey = KeyFactory.getInstance("RSA")
                    .generatePrivate(new PKCS8EncodedKeySpec(Files.readAllBytes(keyFile.toPath())));
            certificate = CertificateFactory.getInstance("X.509")
                    .generateCertificate(new ByteArrayInputStream(Files.readAllBytes(certFile.toPath())));
        } else {
            KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
            generator.initialize(2048);
            KeyPair pair = generator.generateKeyPair();
            X500Name name = new X500Name("CN=Watch Face Installer");
            Date notBefore = new Date(System.currentTimeMillis() - 86_400_000L);
            Date notAfter = new Date(System.currentTimeMillis() + 20L * 365 * 86_400_000L);
            X509v3CertificateBuilder builder = new JcaX509v3CertificateBuilder(
                    name, BigInteger.valueOf(System.currentTimeMillis()), notBefore, notAfter, name, pair.getPublic());
            ContentSigner signer = new JcaContentSignerBuilder("SHA256withRSA").build(pair.getPrivate());
            privateKey = pair.getPrivate();
            certificate = new JcaX509CertificateConverter().getCertificate(builder.build(signer));
            write(keyFile, privateKey.getEncoded());
            write(certFile, certificate.getEncoded());
        }
    }

    private static void write(File file, byte[] data) throws IOException {
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write(data);
        }
    }

    @Override
    protected PrivateKey getPrivateKey() {
        return privateKey;
    }

    @Override
    protected Certificate getCertificate() {
        return certificate;
    }

    @Override
    protected String getDeviceName() {
        return "WatchFaceInstaller";
    }
}
