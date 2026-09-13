package com.ba.bluearchivemusicapi.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.util.ReflectionTestUtils;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectResponse;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class CatalogMediaStorageTest {
    @TempDir Path directory;

    private CatalogMediaStorage storage(S3Client client, String mode) {
        var storage = new CatalogMediaStorage(client);
        ReflectionTestUtils.setField(storage, "mode", mode);
        ReflectionTestUtils.setField(storage, "localRoot", directory.toString());
        ReflectionTestUtils.setField(storage, "bucket", "test");
        return storage;
    }

    private MockMultipartFile audio(byte... bytes) {
        return new MockMultipartFile("audio", "audio.mp3", "application/octet-stream", bytes);
    }

    @Test
    void retriesReuseBytesAndReplacementsLeaveLiveFileIntact() throws Exception {
        var storage = storage(mock(S3Client.class), "local");
        String first = storage.store(audio((byte) 1), "album/track.mp3");
        var timestamp = Files.getLastModifiedTime(directory.resolve(first));
        assertThat(storage.store(audio((byte) 1), "album/track.mp3")).isEqualTo(first);
        assertThat(Files.getLastModifiedTime(directory.resolve(first))).isEqualTo(timestamp);
        String replacement = storage.store(audio((byte) 2), "album/track.mp3");
        assertThat(replacement).isNotEqualTo(first);
        assertThat(Files.readAllBytes(directory.resolve(first))).containsExactly((byte) 1);
        assertThatThrownBy(() -> storage.store(audio(), "album/track.mp3")).isInstanceOf(IllegalArgumentException.class);
        assertThat(Files.readAllBytes(directory.resolve(first))).containsExactly((byte) 1);
    }

    @Test
    void objectRetryDoesNotPutAndNewUploadHasPlayableContentType() {
        var client = mock(S3Client.class);
        var storage = storage(client, "r2");
        String predicted = storage.keyFor(audio((byte) 1), "album/track.mp3");
        verifyNoInteractions(client);
        when(client.headObject(any(HeadObjectRequest.class)))
                .thenThrow(S3Exception.builder().statusCode(404).build())
                .thenReturn(HeadObjectResponse.builder().build());
        String key = storage.store(audio((byte) 1), "album/track.mp3");
        assertThat(key).isEqualTo(predicted);
        assertThat(storage.store(audio((byte) 1), "album/track.mp3")).isEqualTo(key);
        var request = org.mockito.ArgumentCaptor.forClass(PutObjectRequest.class);
        verify(client, times(1)).putObject(request.capture(), any(RequestBody.class));
        assertThat(request.getValue().contentType()).isEqualTo("audio/mpeg");
        assertThat(request.getValue().ifNoneMatch()).isEqualTo("*");
    }

    @Test
    void storageAccessFailureIsNotTreatedAsMissingObject() {
        var client = mock(S3Client.class);
        when(client.headObject(any(HeadObjectRequest.class)))
                .thenThrow(S3Exception.builder().statusCode(403).build());
        assertThatThrownBy(() -> storage(client, "r2").store(audio((byte) 1), "track.mp3"))
                .isInstanceOf(S3Exception.class);
        verify(client, never()).putObject(any(PutObjectRequest.class), any(RequestBody.class));
    }
}
