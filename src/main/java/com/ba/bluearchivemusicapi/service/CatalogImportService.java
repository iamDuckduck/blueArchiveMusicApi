package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.dtos.catalog.CatalogAlbumImportDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogImportResultDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogPerformerDTO;
import com.ba.bluearchivemusicapi.dtos.catalog.CatalogTrackImportDTO;
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

    @Transactional
    public CatalogImportResultDTO publishAlbum(
            String source, String sourceAlbumId, CatalogAlbumImportDTO input,
            MultipartFile original, MultipartFile cover400, MultipartFile cover800) {
        validateIdentity(source, sourceAlbumId);
        Album album = albumRepository.findByImportSourceAndSourceAlbumId(source, sourceAlbumId).orElse(null);
        boolean created = album == null;
        if (created) album = new Album();

        String root = "catalog/" + source + "/albums/" + sourceAlbumId + "/covers/";
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
        return new CatalogImportResultDTO(album.getId(), null, created, created ? "created" : "updated");
    }

    @Transactional
    public CatalogImportResultDTO publishTrack(
            String source, String sourceAlbumId, String sourceTrackId,
            CatalogTrackImportDTO input, MultipartFile audio) {
        validateIdentity(source, sourceAlbumId);
        validateIdentityPart(sourceTrackId);
        if (!KINDS.contains(input.kind())) throw new IllegalArgumentException("Unknown music kind");
        Album album = albumRepository.findByImportSourceAndSourceAlbumId(source, sourceAlbumId)
                .orElseThrow(() -> new IllegalArgumentException("Publish the album before its tracks"));
        Song song = songRepository.findByAlbumIdAndImportSourceAndSourceTrackId(
                album.getId(), source, sourceTrackId).orElse(null);
        boolean created = song == null;
        if (created) song = new Song();

        String audioPath = mediaStorage.store(audio,
                "catalog/" + source + "/albums/" + sourceAlbumId + "/tracks/" + sourceTrackId + "." + extension(audio));
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
        return new CatalogImportResultDTO(album.getId(), song.getId(), created, created ? "created" : "updated");
    }

    private void syncCredits(Song song, CatalogTrackImportDTO input) {
        Set<Credit> desired = new LinkedHashSet<>();
        addNames(desired, input.artists(), SongArtistType.ARTIST);
        addNames(desired, input.composers(), SongArtistType.COMPOSER);
        SongArtistType performerType = "instrumental".equals(input.kind())
                ? SongArtistType.ASSOCIATED : SongArtistType.ARTIST;
        if (input.performers() != null) {
            addNames(desired, input.performers().stream().map(CatalogPerformerDTO::displayName).toList(), performerType);
        }

        song.getSongArtists().removeIf(link -> !desired.contains(
                new Credit(link.getArtist().getName(), link.getType())));
        Set<String> existing = new LinkedHashSet<>();
        song.getSongArtists().forEach(link -> existing.add(link.getArtist().getName() + "\0" + link.getType()));
        desired.forEach(credit -> {
            if (existing.add(credit.name() + "\0" + credit.type())) {
                song.addArtist(findOrCreateArtist(credit.name()), credit.type());
            }
        });
    }

    private void addNames(Set<Credit> result, List<String> names, SongArtistType type) {
        if (names == null) return;
        names.stream().filter(name -> name != null && !name.isBlank())
                .map(String::strip).forEach(name -> result.add(new Credit(name, type)));
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

    private record Credit(String name, SongArtistType type) {}
}
