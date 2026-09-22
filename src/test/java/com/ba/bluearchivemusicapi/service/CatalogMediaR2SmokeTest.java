package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.configuration.CloudflareProperties;
import com.ba.bluearchivemusicapi.configuration.CloudflareR2Config;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.util.ReflectionTestUtils;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;

/** Explicit manual check: writes only to a dev-labelled bucket; never starts Spring or a database. */
@EnabledIfEnvironmentVariable(named = "CATALOG_R2_SMOKE", matches = "true")
class CatalogMediaR2SmokeTest {
    @Test
    void reviewedAudioIsStoredOnceAndPubliclyReadable() throws Exception {
        assertThat(required("SPRING_PROFILES_ACTIVE")).isEqualTo("dev");
        String bucket = required("R2_BUCKET");
        assertThat(bucket).matches(".*(?:^|[-_])dev(?:$|[-_]).*");
        var properties = new CloudflareProperties();
        properties.setEndpoint(required("R2_ENDPOINT"));
        properties.setAccessKey(required("R2_ACCESS_KEY"));
        properties.setSecretKey(required("R2_SECRET_KEY"));
        properties.setBucket(bucket);
        URI endpoint = URI.create(properties.getEndpoint());
        assertThat(endpoint.getScheme()).isEqualTo("https");
        assertThat(endpoint.getHost()).endsWith(".r2.cloudflarestorage.com");

        byte[] bytes = Files.readAllBytes(Path.of(required("CATALOG_SMOKE_AUDIO")));
        var audio = new MockMultipartFile("audio", "audio.mp3", "audio/mpeg", bytes);
        try (var client = new CloudflareR2Config(properties).s3Client()) {
            var storage = new CatalogMediaStorage(client);
            ReflectionTestUtils.setField(storage, "mode", "r2");
            ReflectionTestUtils.setField(storage, "bucket", bucket);
            String key = storage.store(audio, "dev-smoke/veritas/255.mp3");
            var request = HeadObjectRequest.builder().bucket(bucket).key(key).build();
            var first = client.headObject(request);
            assertThat(first.contentType()).isEqualTo("audio/mpeg");
            assertThat(first.contentLength()).isEqualTo((long) bytes.length);
            assertThat(storage.store(audio, "dev-smoke/veritas/255.mp3")).isEqualTo(key);
            var retry = client.headObject(request);
            assertThat(retry.eTag()).isEqualTo(first.eTag());
            assertThat(retry.lastModified()).isEqualTo(first.lastModified());
            // Retain this stable test object. This check never deletes or lists other objects.
            System.out.println("R2 smoke: stored/reused reviewed audio; retained key: " + key);

            URI publicUrl = URI.create(required("CATALOG_SMOKE_PUBLIC_BASE").replaceAll("/+$", "") + "/" + key);
            assertThat(publicUrl.getScheme()).isEqualTo("https");
            var http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(20)).build();
            var response = http.send(HttpRequest.newBuilder(publicUrl)
                    .timeout(Duration.ofSeconds(30)).header("Range", "bytes=0-1023")
                    .header("Origin", "http://localhost:5173").GET().build(),
                    HttpResponse.BodyHandlers.ofByteArray());
            assertThat(response.statusCode()).as("public audio byte-range response").isEqualTo(206);
            assertThat(response.headers().firstValue("Content-Type").orElse("")).startsWith("audio/mpeg");
            assertThat(response.body()).containsExactly(java.util.Arrays.copyOf(bytes, 1024));
            System.out.println("R2 smoke: public MIME and byte range verified; CORS allow-origin: "
                    + response.headers().firstValue("Access-Control-Allow-Origin").orElse("absent"));
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        assertThat(value).as("required environment variable %s", name).isNotBlank();
        return value;
    }
}
