package com.ba.bluearchivemusicapi.controller;

import com.ba.bluearchivemusicapi.entities.Artist;
import com.ba.bluearchivemusicapi.repositories.ArtistRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import com.ba.bluearchivemusicapi.service.CatalogMediaStorage;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMultipartHttpServletRequestBuilder;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:artist-credit-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "spring.jpa.hibernate.ddl-auto=create-drop",
        "app.admin.api-key=artist-credit-test-only",
        "app.catalog-media.mode=local"
})
@ActiveProfiles("test")
@AutoConfigureMockMvc
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
class ArtistCreditIntegrationTest {
    private static final String KEY = "artist-credit-test-only";
    private static final String ALBUM = "/admin/catalog-import/kivo/albums/credit-test";
    private static final String PERFORMER = "チヒロ / 山村響";
    @TempDir static java.nio.file.Path mediaDirectory;

    @DynamicPropertySource
    static void temporaryMedia(DynamicPropertyRegistry registry) {
        registry.add("app.catalog-media.local-root", () -> mediaDirectory.toString());
    }

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired ArtistRepository artists;
    @Autowired SongRepository songs;
    @Autowired JdbcTemplate jdbc;
    @MockitoSpyBean CatalogMediaStorage storage;

    @Test
    void aliasManagementIsProtectedBoundedAndNeverRenamesOrMergesArtists() throws Exception {
        var first = artists.saveAndFlush(Artist.builder().name("ミカ").build());
        var second = artists.saveAndFlush(Artist.builder().name("Another character").build());
        mvc.perform(get("/admin/artist")).andExpect(status().isForbidden());
        mvc.perform(get("/admin/artist/{id}", first.getId())).andExpect(status().isForbidden());
        mvc.perform(put("/admin/artist/{id}/aliases", first.getId()).contentType("application/json")
                .content("{\"aliases\":[\"Mika\"]}")).andExpect(status().isForbidden());

        mvc.perform(put("/admin/artist/{id}/aliases", first.getId()).header("X-Admin-Api-Key", KEY)
                .contentType("application/json").content("{\"aliases\":[\" Mika \",\"未花\",\"Mika\"]}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.name").value("ミカ"))
                .andExpect(jsonPath("$.aliases.length()").value(2));
        // An alias may legitimately be shared, such as an actor on multiple entries.
        mvc.perform(put("/admin/artist/{id}/aliases", second.getId()).header("X-Admin-Api-Key", KEY)
                .contentType("application/json").content("{\"aliases\":[\"Mika\"]}"))
                .andExpect(status().isOk());
        assertThat(artists.count()).isEqualTo(2);
        mvc.perform(get("/admin/artist").param("query", " ミカ ").header("X-Admin-Api-Key", KEY))
                .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].id").value(first.getId()));
        mvc.perform(get("/admin/artist").param("query", "x".repeat(256)).header("X-Admin-Api-Key", KEY))
                .andExpect(status().isBadRequest());
        mvc.perform(get("/admin/artist/{id}", Long.MAX_VALUE).header("X-Admin-Api-Key", KEY))
                .andExpect(status().isNotFound());

        for (String invalid : List.of("{\"aliases\":null}", "{\"aliases\":[\" \" ]}",
                mapper.writeValueAsString(java.util.Map.of("aliases", List.of("x".repeat(256)))),
                mapper.writeValueAsString(java.util.Map.of("aliases", java.util.Collections.nCopies(21, "Alias"))))) {
            mvc.perform(put("/admin/artist/{id}/aliases", first.getId()).header("X-Admin-Api-Key", KEY)
                    .contentType("application/json").content(invalid)).andExpect(status().isBadRequest());
        }
        mvc.perform(get("/admin/artist/{id}", first.getId()).header("X-Admin-Api-Key", KEY))
                .andExpect(jsonPath("$.aliases.length()").value(2));
        mvc.perform(put("/admin/artist/{id}/aliases", first.getId()).header("X-Admin-Api-Key", KEY)
                .contentType("application/json").content("{\"aliases\":[]}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.aliases.length()").value(0));
    }

    @Test
    void existingUploadEndpointKeepsIdAndNameAndReturnsAdditiveProfileFields() throws Exception {
        var created = mvc.perform(post("/admin/artist/upload").header("X-Admin-Api-Key", KEY).param("name", " Nor "))
                .andExpect(status().isOk()).andExpect(jsonPath("$.name").value("Nor"))
                .andExpect(jsonPath("$.aliases.length()").value(0)).andReturn();
        assertThat(mapper.readTree(created.getResponse().getContentAsString()).path("id").asLong()).isPositive();
        mvc.perform(post("/admin/artist/upload").header("X-Admin-Api-Key", KEY).param("name", "Nor"))
                .andExpect(status().isBadRequest());
        assertThat(artists.count()).isEqualTo(1);
    }

    @Test
    void vocalAndInstrumentalReuseOneStructuredEntryWithoutChangingPublicArrays() throws Exception {
        long albumId = publishAlbum();
        mvc.perform(track("255", "Character song", "vocal")).andExpect(status().isOk());
        mvc.perform(track("256", "Instrumental", "instrumental")).andExpect(status().isOk());
        var profile = artists.findByName(PERFORMER).orElseThrow();
        assertThat(profile.getCharacterName()).isEqualTo("チヒロ");
        assertThat(profile.getVoiceActorName()).isEqualTo("山村響");
        assertThat(artists.count()).isEqualTo(1);
        mvc.perform(get("/user/albums/{id}/songs", albumId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.songList[0].artists[0]").value(PERFORMER))
                .andExpect(jsonPath("$.songList[0].associatedArtists.length()").value(0))
                .andExpect(jsonPath("$.songList[1].artists.length()").value(0))
                .andExpect(jsonPath("$.songList[1].associatedArtists[0]").value(PERFORMER));
    }

    @Test
    void identicalLegacyRetryEnrichesProfilesWithoutChangingRevisionMediaOrAliases() throws Exception {
        publishAlbum();
        JsonNode first = mapper.readTree(mvc.perform(track("255", "Character song", "vocal"))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
        var profile = artists.findByName(PERFORMER).orElseThrow();
        mvc.perform(put("/admin/artist/{id}/aliases", profile.getId()).header("X-Admin-Api-Key", KEY)
                .contentType("application/json").content("{\"aliases\":[\"Chihiro\",\"千寻\"]}"))
                .andExpect(status().isOk());
        jdbc.update("UPDATE artist SET character_name = NULL, voice_actor_name = NULL WHERE id = ?", profile.getId());
        clearInvocations(storage);
        mvc.perform(track("255", "Character song", "vocal"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("unchanged"))
                .andExpect(jsonPath("$.revision").value(first.path("revision").asText()))
                .andExpect(jsonPath("$.songId").value(first.path("songId").asLong()));
        verify(storage, never()).store(any(), anyString());
        assertThat(artists.count()).isEqualTo(1);
        assertThat(songs.count()).isEqualTo(1);
        mvc.perform(get("/admin/artist/{id}", profile.getId()).header("X-Admin-Api-Key", KEY))
                .andExpect(jsonPath("$.characterName").value("チヒロ"))
                .andExpect(jsonPath("$.voiceActorName").value("山村響"))
                .andExpect(jsonPath("$.aliases.length()").value(2));
        mvc.perform(get(ALBUM + "/tracks/255").header("X-Admin-Api-Key", KEY))
                .andExpect(jsonPath("$.revision").value(first.path("revision").asText()));
    }

    @Test
    void staleTrackEditsDoNotEnrichProfilesBeforeTheConflictDecision() throws Exception {
        publishAlbum();
        mvc.perform(track("255", "Character song", "vocal")).andExpect(status().isOk());
        var profile = artists.findByName(PERFORMER).orElseThrow();
        jdbc.update("UPDATE artist SET character_name = NULL, voice_actor_name = NULL WHERE id = ?", profile.getId());
        clearInvocations(storage);
        mvc.perform(track("255", "Unreviewed newer title", "vocal")).andExpect(status().isConflict());
        var unchanged = artists.findById(profile.getId()).orElseThrow();
        assertThat(unchanged.getCharacterName()).isNull();
        assertThat(unchanged.getVoiceActorName()).isNull();
        verify(storage, never()).store(any(), anyString());
    }

    @Test
    void contradictoryStructuredProfileIsNotOverwrittenOrUploaded() throws Exception {
        publishAlbum();
        var saved = artists.saveAndFlush(Artist.builder().name(PERFORMER)
                .characterName("Different character").voiceActorName("山村響").build());
        clearInvocations(storage);
        mvc.perform(track("255", "Character song", "vocal")).andExpect(status().isBadRequest());
        assertThat(artists.findById(saved.getId()).orElseThrow().getCharacterName()).isEqualTo("Different character");
        assertThat(songs.count()).isZero();
        verify(storage, never()).store(any(), anyString());
    }

    @Test
    void genericJoinedDisplayNamesAreNotParsedAndAliasesDoNotMergeIdentities() throws Exception {
        publishAlbum();
        var profile = artists.saveAndFlush(Artist.builder().name("Existing person").build());
        mvc.perform(put("/admin/artist/{id}/aliases", profile.getId()).header("X-Admin-Api-Key", KEY)
                .contentType("application/json").content("{\"aliases\":[\"Generic / Label\"]}"))
                .andExpect(status().isOk());
        var request = baseTrack("255", "Generic song", "vocal", "[\"Generic / Label\"]", "[]");
        mvc.perform(request).andExpect(status().isOk());
        var generic = artists.findByName("Generic / Label").orElseThrow();
        assertThat(generic.getCharacterName()).isNull();
        assertThat(generic.getVoiceActorName()).isNull();
        assertThat(generic.getId()).isNotEqualTo(profile.getId());
        assertThat(artists.count()).isEqualTo(2);
    }

    @Test
    void samePlainNameDoesNotCombineACharacterWithAnActorOnlyEntry() throws Exception {
        publishAlbum();
        var actor = artists.saveAndFlush(Artist.builder().name("Shared name").voiceActorName("Shared name").build());
        clearInvocations(storage);
        mvc.perform(baseTrack("255", "Character song", "vocal", "[]", "[{\"character\":\"Shared name\"}]"))
                .andExpect(status().isBadRequest());
        var unchanged = artists.findById(actor.getId()).orElseThrow();
        assertThat(unchanged.getCharacterName()).isNull();
        assertThat(unchanged.getVoiceActorName()).isEqualTo("Shared name");
        assertThat(songs.count()).isZero();
        verify(storage, never()).store(any(), anyString());
    }

    private long publishAlbum() throws Exception {
        var request = multipart(ALBUM);
        request.with(value -> { value.setMethod("PUT"); return value; });
        request.header("X-Admin-Api-Key", KEY);
        request.file(json("{\"title\":\"Credit test\",\"category\":\"Official songs\"}"));
        for (String field : List.of("coverOriginal", "cover400", "cover800")) {
            request.file(new MockMultipartFile(field, "cover.png", "image/png", new byte[]{1, 2, 3}));
        }
        return mapper.readTree(mvc.perform(request).andExpect(status().isOk()).andReturn()
                .getResponse().getContentAsString()).path("albumId").asLong();
    }

    private MockMultipartHttpServletRequestBuilder track(String id, String title, String kind) {
        return baseTrack(id, title, kind, "[]", "[{\"character\":\"チヒロ\",\"voiceActor\":\"山村響\"}]");
    }

    private MockMultipartHttpServletRequestBuilder baseTrack(String id, String title, String kind, String artists, String performers) {
        var request = multipart(ALBUM + "/tracks/" + id);
        request.with(value -> { value.setMethod("PUT"); return value; });
        request.header("X-Admin-Api-Key", KEY);
        request.file(json("""
                {"title":"%s","displayOrder":%s,"kind":"%s","artists":%s,"performers":%s}
                """.formatted(title, id, kind, artists, performers)));
        request.file(new MockMultipartFile("audio", "audio.mp3", "audio/mpeg", new byte[]{4, 5, 6}));
        return request;
    }

    private MockMultipartFile json(String value) {
        return new MockMultipartFile("metadata", "metadata.json", "application/json", value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
}
