package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.dtos.catalog.CatalogAlbumImportDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogImportResultDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogTrackImportDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogImportStateDTO;
import com.ba.bluearchivemusicapi.common.exception.CatalogConflictException;
import com.ba.bluearchivemusicapi.entities.*;
import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.ArtistRepository;
import com.ba.bluearchivemusicapi.repositories.CategoryRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class CatalogImportService {
    private static final Set<String> KINDS = Set.of("vocal", "instrumental", "bgm", "unsure");

    private final AlbumRepository albumRepository;
    private final SongRepository songRepository;
    private final CategoryRepository categoryRepository;
    private final ArtistRepository artistRepository;
    private final CatalogMediaStorage mediaStorage;
    private final CatalogImportSnapshot snapshots;

    @Transactional
    public CatalogImportResultDTO publishAlbum(
            String source, String sourceAlbumId, CatalogAlbumImportDTO input,
            MultipartFile original, MultipartFile cover400, MultipartFile cover800, String expectedRevision) {
        validateIdentity(source, sourceAlbumId);
        Album album = albumRepository.findImportForUpdate(source, sourceAlbumId).orElse(null);
        boolean created = album == null;
        String root = "catalog/" + source + "/albums/" + sourceAlbumId + "/covers/";
        CatalogImportStateDTO current = snapshots.album(album);
        CatalogImportStateDTO desired = snapshots.state(current.albumId(), null, CatalogImportSnapshot.albumFields(input),
                CatalogImportSnapshot.albumMedia(mediaStorage.keyFor(original, root + "original." + extension(original)),
                        mediaStorage.keyFor(cover400, root + "400.jpg"), mediaStorage.keyFor(cover800, root + "800.jpg")));
        if (!checkRevision(current, desired, expectedRevision)) return result(current, false, "unchanged");
        if (created) album = new Album();
        String originalPath = mediaStorage.store(original, root + "original." + extension(original));
        String cover400Path = mediaStorage.store(cover400, root + "400.jpg");
        String cover800Path = mediaStorage.store(cover800, root + "800.jpg");
        Category category = categoryRepository.findByCategory(input.category());
        if (category == null) category = categoryRepository.save(Category.builder().category(input.category()).build());

        album.setTitle(input.title().strip());
        album.setReleaseDate(input.releaseDate());
        album.setDescription(input.description());
        album.setCategory(category);
        album.setCoverOriginalPath(originalPath);
        album.setCover400Path(cover400Path);
        album.setCover800Path(cover800Path);
        album.setCoverImagePath(cover800Path);
        album.setImportSource(source);
        album.setSourceAlbumId(sourceAlbumId);
        album = albumRepository.save(album);
        return result(snapshots.album(album), created, created ? "created" : "updated");
    }

    @Transactional
    public CatalogImportResultDTO publishTrack(
            String source, String sourceAlbumId, String sourceTrackId,
            CatalogTrackImportDTO input, MultipartFile audio, String expectedRevision) {
        validateIdentity(source, sourceAlbumId);
        validateIdentityPart(sourceTrackId);
        if (!KINDS.contains(input.kind())) throw new IllegalArgumentException("Unknown music kind");
        Album album = albumRepository.findImportForUpdate(source, sourceAlbumId)
                .orElseThrow(() -> new IllegalArgumentException("Publish the album before its tracks"));
        Song song = songRepository.findImportForUpdate(
                album.getId(), source, sourceTrackId).orElse(null);
        boolean created = song == null;
        String audioKey = "catalog/" + source + "/albums/" + sourceAlbumId + "/tracks/" + sourceTrackId + "." + extension(audio);
        CatalogImportStateDTO current = snapshots.track(song);
        CatalogImportStateDTO desired = snapshots.state(album.getId(), current.songId(), CatalogImportSnapshot.trackFields(input),
                CatalogImportSnapshot.trackMedia(mediaStorage.keyFor(audio, audioKey), album.getCover400Path()));
        if (!checkRevision(current, desired, expectedRevision)) return result(current, false, "unchanged");
        if (created) song = new Song();

        String audioPath = mediaStorage.store(audio, audioKey);
        song.setTitle(input.title().strip());
        song.setDescription(input.description());
        song.setDiscNumber(input.disc());
        song.setTrackNumber(input.position());
        song.setDisplayOrder(input.displayOrder());
        song.setMusicKind(input.kind());
        song.setAudioPath(audioPath);
        song.setImagePath(album.getCover400Path());
        song.setAlbum(album);
        song.setImportSource(source);
        song.setSourceTrackId(sourceTrackId);
        if (song.getPlayCount() == null) song.setPlayCount(0L);
        syncCredits(song, input);
        song = songRepository.save(song);
        return result(snapshots.track(song), created, created ? "created" : "updated");
    }

    @Transactional(readOnly = true)
    public CatalogImportStateDTO albumState(String source, String identity) {
        validateIdentity(source, identity);
        return snapshots.album(albumRepository.findByImportSourceAndSourceAlbumId(source, identity).orElse(null));
    }

    @Transactional(readOnly = true)
    public CatalogImportStateDTO trackState(String source, String identity, String trackId) {
        validateIdentity(source, identity);
        validateIdentityPart(trackId);
        Album album = albumRepository.findByImportSourceAndSourceAlbumId(source, identity).orElse(null);
        if (album == null) return CatalogImportStateDTO.missing();
        return snapshots.track(songRepository.findByAlbumIdAndImportSourceAndSourceTrackId(album.getId(), source, trackId).orElse(null));
    }

    private boolean checkRevision(CatalogImportStateDTO current, CatalogImportStateDTO desired, String expected) {
        // No write is needed for identical content, including after a lost successful response.
        if (current.exists() && current.revision().equals(desired.revision())) return false;
        if (!java.util.Objects.equals(current.revision(), expected)) throw new CatalogConflictException(current);
        return true;
    }

    private CatalogImportResultDTO result(CatalogImportStateDTO state, boolean created, String status) {
        return new CatalogImportResultDTO(state.albumId(), state.songId(), created, status, state.revision());
    }

    private void syncCredits(Song song, CatalogTrackImportDTO input) {
        List<CatalogImportSnapshot.Credit> desired = CatalogImportSnapshot.credits(input);

        song.getSongArtists().removeIf(link -> !desired.contains(
                new CatalogImportSnapshot.Credit(link.getArtist().getName(), link.getType())));
        Set<String> existing = new LinkedHashSet<>();
        song.getSongArtists().forEach(link -> existing.add(link.getArtist().getName() + "\0" + link.getType()));
        desired.forEach(credit -> {
            if (existing.add(credit.name() + "\0" + credit.type())) {
                song.addArtist(findOrCreateArtist(credit.name()), credit.type());
            }
        });
    }

    private Artist findOrCreateArtist(String name) {
        return artistRepository.findByName(name)
                .orElseGet(() -> artistRepository.save(Artist.builder().name(name).build()));
    }

    private void validateIdentity(String source, String sourceAlbumId) {
        validateIdentityPart(source);
        if (source.length() > 64) throw new IllegalArgumentException("Import source exceeds 64 characters");
        validateIdentityPart(sourceAlbumId);
    }

    private void validateIdentityPart(String value) {
        if (value == null || !value.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,254}")) {
            throw new IllegalArgumentException("Import identities may contain letters, digits, dot, underscore and dash only");
        }
    }

    private String extension(MultipartFile file) {
        String name = file.getOriginalFilename();
        if (name == null || !name.contains(".")) throw new IllegalArgumentException("Media filename needs an extension");
        String extension = name.substring(name.lastIndexOf('.') + 1).toLowerCase();
        if (!extension.matches("[a-z0-9]{2,5}")) throw new IllegalArgumentException("Invalid media extension");
        return extension;
    }

}
