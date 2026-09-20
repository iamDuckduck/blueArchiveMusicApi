package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.dtos.search.AlbumSearchResultDTO;
import com.ba.bluearchivemusicapi.dtos.search.SongSearchResultDTO;
import com.ba.bluearchivemusicapi.mappers.MusicSearchMapper;
import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import com.ba.bluearchivemusicapi.repositories.projection.AlbumSearchProjection;
import com.ba.bluearchivemusicapi.repositories.projection.SongSearchProjection;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

/** Service contract only; native pg_trgm/EXISTS behavior requires PostgreSQL verification. */
@ExtendWith(MockitoExtension.class)
class MusicSearchServiceTest {
    @Mock AlbumRepository albums;
    @Mock SongRepository songs;
    @Mock MusicSearchMapper mapper;
    @InjectMocks MusicSearchService service;

    @Test
    void blankInputReturnsEmptySectionsWithoutQueryingTheCatalog() {
        var result = service.search(" \t\n ");

        assertThat(result.getAlbums()).isEmpty();
        assertThat(result.getSongs()).isEmpty();
        verifyNoInteractions(albums, songs, mapper);
    }

    @Test
    void creditQueryUsesCatalogSearchWithExistingLimitsAndResponseShape() {
        var albumRows = List.of(mock(AlbumSearchProjection.class));
        var songRows = List.of(mock(SongSearchProjection.class));
        var albumResults = List.of(new AlbumSearchResultDTO());
        var songResults = List.of(new SongSearchResultDTO());
        when(albums.searchCatalog("山村響", 5)).thenReturn(albumRows);
        when(songs.searchCatalog("山村響", 5)).thenReturn(songRows);
        when(mapper.toAlbumSearchResults(albumRows)).thenReturn(albumResults);
        when(mapper.toSongSearchResults(songRows)).thenReturn(songResults);

        var result = service.search("  山村響  ");

        assertThat(result.getAlbums()).isSameAs(albumResults);
        assertThat(result.getSongs()).isSameAs(songResults);
        verify(albums).searchCatalog("山村響", 5);
        verify(songs).searchCatalog("山村響", 5);
    }

    @Test
    void excessiveInputIsRejectedBeforeDatabaseWork() {
        assertThatThrownBy(() -> service.search("a".repeat(256)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("255");

        verifyNoInteractions(albums, songs, mapper);
    }

    @Test
    void maximumLengthInputRemainsAQueryParameterAndResultsStayBounded() {
        String query = "a".repeat(255);
        when(albums.searchCatalog(query, 5)).thenReturn(List.of());
        when(songs.searchCatalog(query, 5)).thenReturn(List.of());
        when(mapper.toAlbumSearchResults(List.of())).thenReturn(List.of());
        when(mapper.toSongSearchResults(List.of())).thenReturn(List.of());

        var result = service.search(query);

        assertThat(result.getAlbums()).isEmpty();
        assertThat(result.getSongs()).isEmpty();
        verify(albums).searchCatalog(query, 5);
        verify(songs).searchCatalog(query, 5);
    }
}
