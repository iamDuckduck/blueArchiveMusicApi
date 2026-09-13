package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.dtos.catalog.*;
import com.ba.bluearchivemusicapi.entities.*;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;

/** Content-only baselines: plays and audit dates must not invalidate reviewed edits. */
@Component
@RequiredArgsConstructor
public class CatalogImportSnapshot {
    private final ObjectMapper mapper;

    public CatalogImportStateDTO album(Album album) {
        if (album == null) return CatalogImportStateDTO.missing();
        Map<String, String> media = albumMedia(album.getCoverOriginalPath(), album.getCover400Path(), album.getCover800Path());
        media.put("coverImage", album.getCoverImagePath());
        return state(album.getId(), null, albumFields(new CatalogAlbumImportDTO(album.getTitle(),
                album.getCategory().getCategory(), album.getReleaseDate(), album.getDescription())),
                media);
    }

    public CatalogImportStateDTO track(Song song) {
        if (song == null) return CatalogImportStateDTO.missing();
        Map<String, Object> fields = trackFields(new CatalogTrackImportDTO(song.getTitle(), song.getDiscNumber(),
                song.getTrackNumber(), song.getDisplayOrder(), song.getMusicKind(), song.getDescription(), null, null, null));
        fields.put("credits", sorted(song.getSongArtists().stream()
                .map(link -> new Credit(link.getArtist().getName(), link.getType())).toList()));
        return state(song.getAlbum().getId(), song.getId(), fields, trackMedia(song.getAudioPath(), song.getImagePath()));
    }

    public CatalogImportStateDTO state(Long albumId, Long songId, Map<String, Object> fields, Map<String, String> media) {
        try {
            String revision = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(mapper.writeValueAsBytes(List.of(fields, media))));
            return new CatalogImportStateDTO(true, albumId, songId, revision, fields, media);
        } catch (NoSuchAlgorithmException | JsonProcessingException error) {
            throw new IllegalStateException("Cannot fingerprint catalog content", error);
        }
    }

    public static Map<String, Object> albumFields(CatalogAlbumImportDTO input) {
        Map<String, Object> fields = new TreeMap<>();
        fields.put("title", input.title().strip());
        fields.put("category", input.category());
        fields.put("releaseDate", input.releaseDate() == null ? null : input.releaseDate().toString());
        fields.put("description", input.description());
        return fields;
    }

    public static Map<String, Object> trackFields(CatalogTrackImportDTO input) {
        Map<String, Object> fields = new TreeMap<>();
        fields.put("title", input.title().strip());
        fields.put("disc", input.disc());
        fields.put("position", input.position());
        fields.put("displayOrder", input.displayOrder());
        fields.put("kind", input.kind());
        fields.put("description", input.description());
        fields.put("credits", sorted(credits(input)));
        return fields;
    }

    public static Map<String, String> albumMedia(String original, String cover400, String cover800) {
        Map<String, String> media = new TreeMap<>();
        media.put("coverOriginal", original);
        media.put("cover400", cover400);
        media.put("cover800", cover800);
        media.put("coverImage", cover800);
        return media;
    }

    public static Map<String, String> trackMedia(String audio, String image) {
        Map<String, String> media = new TreeMap<>();
        media.put("audio", audio);
        media.put("image", image);
        return media;
    }

    public static List<Credit> credits(CatalogTrackImportDTO input) {
        List<Credit> result = new ArrayList<>();
        add(result, input.artists(), SongArtistType.ARTIST);
        add(result, input.composers(), SongArtistType.COMPOSER);
        if (input.performers() != null) add(result, input.performers().stream().map(CatalogPerformerDTO::displayName).toList(),
                "instrumental".equals(input.kind()) ? SongArtistType.ASSOCIATED : SongArtistType.ARTIST);
        return result.stream().distinct().toList();
    }

    private static void add(List<Credit> result, List<String> names, SongArtistType type) {
        if (names != null) names.stream().filter(name -> name != null && !name.isBlank())
                .map(String::strip).forEach(name -> result.add(new Credit(name, type)));
    }

    private static List<Credit> sorted(List<Credit> credits) {
        return credits.stream().distinct().sorted(Comparator.comparing((Credit credit) -> credit.type().name())
                .thenComparing(Credit::name)).toList();
    }

    public record Credit(String name, SongArtistType type) {}
}
