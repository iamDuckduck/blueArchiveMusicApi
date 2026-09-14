package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.common.exception.FileUploadException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class CatalogMediaStorage {
    private static final Map<String, String> TYPES = Map.of(
            "jpg", "image/jpeg", "jpeg", "image/jpeg", "png", "image/png", "webp", "image/webp",
            "mp3", "audio/mpeg", "wav", "audio/wav", "ogg", "audio/ogg", "m4a", "audio/mp4", "flac", "audio/flac");
    private final S3Client s3Client;

    @Value("${app.catalog-media.mode:r2}")
    private String mode;

    @Value("${app.catalog-media.local-root:./.catalog-import/media}")
    private String localRoot;

    @Value("${cloudflare.r2.bucket}")
    private String bucket;

    public String store(MultipartFile file, String logicalKey) {
        String extension = logicalKey.substring(logicalKey.lastIndexOf('.') + 1);
        String type = TYPES.get(extension);
        if (file.isEmpty() || type == null) throw new IllegalArgumentException("Empty or unsupported catalog media");
        try {
            byte[] bytes = file.getBytes();
            // Immutable keys keep a failed replacement from damaging the live file.
            // Hashing the logical identity also bounds the key length for existing SQL columns.
            String key = "catalog/" + hash(logicalKey.getBytes(StandardCharsets.UTF_8))
                    + "/" + hash(bytes) + "." + extension;
            if ("local".equals(mode)) {
                Path root = Path.of(localRoot).toAbsolutePath().normalize();
                Path target = root.resolve(key).normalize();
                if (!target.startsWith(root)) throw new IllegalArgumentException("Invalid media key");
                if (Files.exists(target)) return key;
                Files.createDirectories(target.getParent());
                Path pending = Files.createTempFile(target.getParent(), ".upload-", ".tmp");
                try {
                    Files.write(pending, bytes);
                    try {
                        Files.move(pending, target);
                    } catch (java.nio.file.FileAlreadyExistsException ignored) {
                        // Another identical request completed the same immutable object.
                    }
                } finally {
                    Files.deleteIfExists(pending);
                }
            } else {
                try {
                    s3Client.headObject(HeadObjectRequest.builder().bucket(bucket).key(key).build());
                    return key;
                } catch (S3Exception missing) {
                    if (missing.statusCode() != 404) throw missing;
                }
                try {
                    s3Client.putObject(PutObjectRequest.builder()
                                    .bucket(bucket).key(key).contentType(type).ifNoneMatch("*").build(),
                            RequestBody.fromBytes(bytes));
                } catch (S3Exception conflict) {
                    if (conflict.statusCode() != 412) throw conflict;
                    return key;
                }
            }
            recordPossibleOrphan(key);
            return key;
        } catch (IOException e) {
            throw new FileUploadException("Failed to store catalog media", e);
        }
    }

    private String hash(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private void recordPossibleOrphan(String key) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) return;
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCompletion(int status) {
                if (status != STATUS_COMMITTED) {
                    log.warn("Catalog transaction did not commit; media may be unreferenced (check before cleanup): {}", key);
                }
            }
        });
    }
}
