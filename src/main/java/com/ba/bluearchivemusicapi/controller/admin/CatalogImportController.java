package com.ba.bluearchivemusicapi.controller.admin;

import com.ba.bluearchivemusicapi.dtos.catalog.CatalogAlbumImportDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogImportResultDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogTrackImportDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogImportStateDTO;
import com.ba.bluearchivemusicapi.common.exception.CatalogConflictException;
import com.ba.bluearchivemusicapi.service.CatalogImportService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/admin/catalog-import")
@RequiredArgsConstructor
public class CatalogImportController {
    private final CatalogImportService catalogImportService;

    @PutMapping("/{source}/albums/{sourceAlbumId}")
    public ResponseEntity<CatalogImportResultDTO> publishAlbum(
            @PathVariable String source,
            @PathVariable String sourceAlbumId,
            @Valid @RequestPart("metadata") CatalogAlbumImportDTO metadata,
            @RequestPart("coverOriginal") MultipartFile coverOriginal,
            @RequestPart("cover400") MultipartFile cover400,
            @RequestPart("cover800") MultipartFile cover800,
            @RequestHeader(value = "X-Catalog-Revision", required = false) String expectedRevision) {
        return ResponseEntity.ok(catalogImportService.publishAlbum(
                source, sourceAlbumId, metadata, coverOriginal, cover400, cover800, expectedRevision));
    }

    @PutMapping("/{source}/albums/{sourceAlbumId}/tracks/{sourceTrackId}")
    public ResponseEntity<CatalogImportResultDTO> publishTrack(
            @PathVariable String source,
            @PathVariable String sourceAlbumId,
            @PathVariable String sourceTrackId,
            @Valid @RequestPart("metadata") CatalogTrackImportDTO metadata,
            @RequestPart("audio") MultipartFile audio,
            @RequestHeader(value = "X-Catalog-Revision", required = false) String expectedRevision) {
        return ResponseEntity.ok(catalogImportService.publishTrack(
                source, sourceAlbumId, sourceTrackId, metadata, audio, expectedRevision));
    }

    @GetMapping("/{source}/albums/{sourceAlbumId}")
    public CatalogImportStateDTO albumState(@PathVariable String source, @PathVariable String sourceAlbumId) {
        return catalogImportService.albumState(source, sourceAlbumId);
    }

    @GetMapping("/{source}/albums/{sourceAlbumId}/tracks/{sourceTrackId}")
    public CatalogImportStateDTO trackState(@PathVariable String source, @PathVariable String sourceAlbumId, @PathVariable String sourceTrackId) {
        return catalogImportService.trackState(source, sourceAlbumId, sourceTrackId);
    }

    @ExceptionHandler(CatalogConflictException.class)
    public ResponseEntity<?> conflict(CatalogConflictException error) {
        return ResponseEntity.status(409).body(java.util.Map.of("error", error.getMessage(), "current", error.getCurrent()));
    }
}
