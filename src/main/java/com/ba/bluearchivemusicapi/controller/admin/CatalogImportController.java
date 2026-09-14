package com.ba.bluearchivemusicapi.controller.admin;

import com.ba.bluearchivemusicapi.dtos.catalog.CatalogAlbumImportDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogImportResultDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogTrackImportDTO;
import com.ba.bluearchivemusicapi.service.CatalogImportService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
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
            @RequestPart("cover800") MultipartFile cover800) {
        return ResponseEntity.ok(catalogImportService.publishAlbum(
                source, sourceAlbumId, metadata, coverOriginal, cover400, cover800));
    }

    @PutMapping("/{source}/albums/{sourceAlbumId}/tracks/{sourceTrackId}")
    public ResponseEntity<CatalogImportResultDTO> publishTrack(
            @PathVariable String source,
            @PathVariable String sourceAlbumId,
            @PathVariable String sourceTrackId,
            @Valid @RequestPart("metadata") CatalogTrackImportDTO metadata,
            @RequestPart("audio") MultipartFile audio) {
        return ResponseEntity.ok(catalogImportService.publishTrack(
                source, sourceAlbumId, sourceTrackId, metadata, audio));
    }
}
