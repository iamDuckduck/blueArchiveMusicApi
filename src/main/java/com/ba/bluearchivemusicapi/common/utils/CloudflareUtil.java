package com.ba.bluearchivemusicapi.common.utils;

import com.ba.bluearchivemusicapi.common.constant.MessageConstant;
import com.ba.bluearchivemusicapi.common.exception.UnsupportedMediaTypeException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;
import software.amazon.awssdk.services.s3.presigner.model.PresignedGetObjectRequest;

import java.time.Duration;
import java.util.Optional;
import java.util.UUID;

@Component
@RequiredArgsConstructor
public class CloudflareUtil {
    private final S3Presigner s3Presigner;

    @Value("${cloudflare.r2.bucket}")
    private String bucket;

    public PutObjectRequest createPutObjectReq(MultipartFile file) {

        // Resolve filename and content type
        String original = Optional.ofNullable(file.getOriginalFilename())
                .orElseThrow(() -> new UnsupportedMediaTypeException(MessageConstant.MISSING_FILENAME))
                .toLowerCase();

        String contentType = Optional.ofNullable(file.getContentType())
                .orElseThrow(() -> new UnsupportedMediaTypeException(MessageConstant.UNKNOWN_CONTENT_TYPE));

        // Decide folder by extension
        String ext = getFileExtension(original);
        String folder = switch (ext) {
            case "jpg", "jpeg", "png" -> "OST/coverImages";
            case "mp3", "wav" -> "OST/audio";
            default -> throw new UnsupportedMediaTypeException("Unsupported type: " + contentType);
        };

        // Build object key
        String key = String.format("%s/%s-%s", folder, UUID.randomUUID(), original);

        // Return PutObjectRequest
        return PutObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .contentType(contentType)
                .build();
    }


    private String getFileExtension(String filename) {
        int idx = filename.lastIndexOf('.');
        if (idx < 0 || idx == filename.length() - 1) {
            throw new IllegalArgumentException("Invalid file extension in filename: " + filename);
        }
        return filename.substring(idx + 1);
    }

    public String generatePresignedDownloadUrl(String bucketName, String objectKey, Duration expiration) {
        GetObjectPresignRequest presignRequest = GetObjectPresignRequest.builder()
                .signatureDuration(expiration)
                .getObjectRequest(builder -> builder
                        .bucket(bucketName)
                        .key(objectKey)
                        .build())
                .build();

        PresignedGetObjectRequest presignedRequest = s3Presigner.presignGetObject(presignRequest);
        return presignedRequest.url().toString();
    }
}
