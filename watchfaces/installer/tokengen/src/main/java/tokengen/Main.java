package tokengen;

import java.io.File;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Collection;

/**
 * Validates Watch Face Push APKs and writes their validation tokens.
 *
 * <pre>usage: Main &lt;marketplace package&gt; &lt;output dir&gt; &lt;apk&gt;=&lt;id&gt; ...</pre>
 *
 * Writes {@code <output dir>/<id>_token.txt} for each APK, or exits non-zero listing the failures.
 * The validator is a Kotlin library; it's called reflectively so this works whether its factory
 * is a static method or a Kotlin object.
 */
public final class Main {
    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            throw new IllegalArgumentException("usage: Main <marketplace package> <output dir> <apk>=<id> ...");
        }
        String marketplace = args[0];
        File outDir = new File(args[1]);
        outDir.mkdirs();
        Object validator = createValidator();
        Method validate = validator.getClass().getMethod("validate", File.class, String.class);
        validate.setAccessible(true);
        boolean failed = false;
        for (int i = 2; i < args.length; i++) {
            String[] parts = args[i].split("=", 2);
            File apk = new File(parts[0]);
            String id = parts[1];
            Object result = validate.invoke(validator, apk, marketplace);
            Collection<?> failures = (Collection<?>) call(result, "failures", "getFailures");
            if (!failures.isEmpty()) {
                failed = true;
                System.err.println(apk.getName() + " failed Watch Face Push validation:");
                for (Object f : failures) {
                    System.err.println("  - " + f);
                }
                continue;
            }
            String token = (String) call(result, "validationToken", "getValidationToken");
            if (token == null || token.isEmpty()) {
                throw new IllegalStateException("No token generated for " + apk.getName());
            }
            Files.writeString(new File(outDir, id + "_token.txt").toPath(), token, StandardCharsets.UTF_8);
            System.out.println(apk.getName() + ": validation passed, token written");
        }
        if (failed) {
            System.exit(1);
        }
    }

    private static Object createValidator() throws Exception {
        Class<?> factory = Class.forName("com.google.android.wearable.watchface.validator.client.DwfValidatorFactory");
        Method create = factory.getMethod("create");
        if (java.lang.reflect.Modifier.isStatic(create.getModifiers())) {
            return create.invoke(null);
        }
        return create.invoke(factory.getField("INSTANCE").get(null)); // Kotlin object
    }

    private static Object call(Object target, String... names) throws Exception {
        for (String name : names) {
            try {
                Method m = target.getClass().getMethod(name);
                m.setAccessible(true);
                return m.invoke(target);
            } catch (NoSuchMethodException ignored) {
            }
        }
        throw new NoSuchMethodException(target.getClass().getName() + " has none of " + String.join(", ", names));
    }
}
