package com.ba.bluearchivemusicapi.common.utils;

import com.ba.bluearchivemusicapi.dtos.album.AlbumDTO;
import lombok.AccessLevel;
import lombok.NoArgsConstructor;

import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@NoArgsConstructor(access = AccessLevel.PRIVATE)
public final class AlbumTitleVolumeOrder {

    private static final Pattern VOLUME_PATTERN =
            Pattern.compile("\\bvol\\.?\\s*(\\d+)\\b", Pattern.CASE_INSENSITIVE);

    public static void sort(List<AlbumDTO> albums) {
        albums.sort(
                Comparator.comparing(
                                AlbumTitleVolumeOrder::volumeNumber,
                                Comparator.nullsLast(Comparator.naturalOrder()))
                        .thenComparing(AlbumDTO::getTitle, String.CASE_INSENSITIVE_ORDER)
                        .thenComparing(AlbumDTO::getId)
        );
    }

    private static Integer volumeNumber(AlbumDTO album) {
        Matcher matcher = VOLUME_PATTERN.matcher(album.getTitle());
        return matcher.find() ? Integer.valueOf(matcher.group(1)) : null;
    }
}
