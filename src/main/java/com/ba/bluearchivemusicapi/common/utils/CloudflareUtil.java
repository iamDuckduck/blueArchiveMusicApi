package com.ba.bluearchivemusicapi.common.utils;

import com.ba.bluearchivemusicapi.common.constant.MessageConstant;
import com.ba.bluearchivemusicapi.common.constant.UploadResourceType;
import com.ba.bluearchivemusicapi.common.exception.FileUploadException;
import com.ba.bluearchivemusicapi.common.exception.UnsupportedMediaTypeException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;
import software.amazon.awssdk.services.s3.presigner.model.PresignedGetObjectRequest;

import java.io.IOException;
import java.time.Duration;
import java.util.Optional;
import java.util.UUID;

@Component
@RequiredArgsConstructor
public class CloudflareUtil {

    private final S3Presigner s3Presigner;

    private final S3Client s3Client;

    @Value("${cloudflare.r2.bucket}")
    private String bucket;

    public PutObjectRequest createPutObjectReq(MultipartFile file, UploadResourceType uploadPath) {

        // Resolve filename and content type
        String original = Optional.ofNullable(file.getOriginalFilename())
                .orElseThrow(() -> new UnsupportedMediaTypeException(MessageConstant.MISSING_FILENAME))
                .toLowerCase();

        String contentType = Optional.ofNullable(file.getContentType())
                .orElseThrow(() -> new UnsupportedMediaTypeException(MessageConstant.UNKNOWN_CONTENT_TYPE));

        // Decide folder by extension
        String ext = getFileExtension(original);
        String folder = switch (ext) {
            case "jpg", "jpeg", "png" -> uploadPath.coverImagePath;
            case "mp3", "wav" -> uploadPath.audioPath;
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

    public String uploadFileToBucket(MultipartFile file, UploadResourceType resourceType) {
        // create Req object to the bucket
        PutObjectRequest req = createPutObjectReq(file, resourceType);

        // todo: handle one failed, one success situation(?)
        // save image and audio in Cloudflare bucket
        try {
            s3Client.putObject(req, RequestBody.fromBytes(file.getBytes()));
        } catch (IOException e) {
            throw new FileUploadException(MessageConstant.FAILED_FILE_UPLOAD_R2, e);
        }

        // get keys (location of the file)
        return req.key();
    }

    // not used as url turned into public, but keep it for future use if needed
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
