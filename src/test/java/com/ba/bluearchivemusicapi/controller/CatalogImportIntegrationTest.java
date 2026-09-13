package com.ba.bluearchivemusicapi.controller;

import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import com.ba.bluearchivemusicapi.service.SongService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMultipartHttpServletRequestBuilder;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:catalog-import-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "spring.jpa.hibernate.ddl-auto=create-drop",
        "app.admin.api-key=catalog-import-test-only",
        "app.catalog-media.mode=local"
})
@ActiveProfiles("test")
@AutoConfigureMockMvc
@org.springframework.test.annotation.DirtiesContext(classMode = org.springframework.test.annotation.DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
class CatalogImportIntegrationTest {
    private static final String KEY = "catalog-import-test-only";
    @TempDir static java.nio.file.Path mediaDirectory;

    @DynamicPropertySource
    static void temporaryMedia(DynamicPropertyRegistry registry) {
        registry.add("app.catalog-media.local-root", () -> mediaDirectory.toString());
    }

    @Autowired MockMvc mockMvc;
    @Autowired AlbumRepository albumRepository;
    @Autowired SongRepository songRepository;
    @Autowired SongService songService;
    @Autowired com.fasterxml.jackson.databind.ObjectMapper mapper;

    @Test
    void repeatedPublicationPreservesIdsCreditsPlayCountAndStoredBytes() throws Exception {
        mockMvc.perform(albumRequest().with(request -> {
            request.removeHeader("X-Admin-Api-Key");
            return request;
        })).andExpect(status().isForbidden());
        assertThat(albumRepository.count()).isZero();
        mockMvc.perform(trackRequest()).andExpect(status().isBadRequest());
        assertThat(songRepository.count()).isZero();

        for (int attempt = 0; attempt < 2; attempt++) {
            mockMvc.perform(albumRequest()).andExpect(status().isOk())
                    .andExpect(jsonPath("$.albumId").isNumber())
                    .andExpect(jsonPath("$.created").value(attempt == 0));
            mockMvc.perform(trackRequest()).andExpect(status().isOk())
                    .andExpect(jsonPath("$.songId").isNumber())
                    .andExpect(jsonPath("$.created").value(attempt == 0));
        }

        assertThat(albumRepository.count()).isEqualTo(1);
        assertThat(songRepository.count()).isEqualTo(1);
        long albumId = albumRepository.findAll().get(0).getId();
        mockMvc.perform(get("/user/albums/{id}/songs", albumId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title").value("青春あんさんぶる Vol.2 「ヴェリタス」"))
                .andExpect(jsonPath("$.category").value("青春あんさんぶる"))
                .andExpect(jsonPath("$.songList[0].title").value("Get Over the World"))
                .andExpect(jsonPath("$.songList[0].trackNumber").value(1))
                .andExpect(jsonPath("$.songList[0].artists[0]").value("Veritas"))
                .andExpect(jsonPath("$.songList[0].composers[0]").value("Veritas"));

        String audioPath = songRepository.findAll().get(0).getAudioPath();
        java.nio.file.Path audioFile = mediaDirectory.resolve(audioPath);
        var modified = java.nio.file.Files.getLastModifiedTime(audioFile);
        assertThat(java.nio.file.Files.readAllBytes(audioFile)).containsExactly(0, 1, 2, 3, 4, 5);

        long songId = songRepository.findAll().get(0).getId();
        for (int play = 0; play < 7; play++) {
            mockMvc.perform(post("/user/song/{id}/play", songId)).andExpect(status().isAccepted());
        }
        // Retry after a success response was lost: IDs, credits, play count and bytes survive.
        mockMvc.perform(albumRequest()).andExpect(status().isOk())
                .andExpect(jsonPath("$.albumId").value(albumId))
                .andExpect(jsonPath("$.created").value(false));
        mockMvc.perform(trackRequest()).andExpect(status().isOk())
                .andExpect(jsonPath("$.songId").value(songId)).andExpect(jsonPath("$.created").value(false));
        assertThat(java.nio.file.Files.getLastModifiedTime(audioFile)).isEqualTo(modified);
        assertThat(songRepository.findById(songId).orElseThrow().getPlayCount()).isEqualTo(7);
        assertThat(albumRepository.count()).isEqualTo(1);
        assertThat(songRepository.count()).isEqualTo(1);
    }

    @Test
    void displayOrderDoesNotInventOfficialNumbersAndRetriesKeepGaps() throws Exception {
        mockMvc.perform(albumRequest()).andExpect(status().isOk());
        mockMvc.perform(trackRequest()).andExpect(status().isOk());
        long albumId = albumRepository.findAll().get(0).getId();
        for (int attempt = 0; attempt < 2; attempt++) {
            mockMvc.perform(orderedTrack("600", "Unknown numbering", "null", "null", 10)).andExpect(status().isOk());
            mockMvc.perform(orderedTrack("601", "Second disc track four", "2", "4", 30)).andExpect(status().isOk());
        }
        assertThat(songRepository.count()).isEqualTo(3);
        mockMvc.perform(get("/user/albums/{id}/songs", albumId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.songList[0].title").value("Unknown numbering"))
                .andExpect(jsonPath("$.songList[0].discNumber").isEmpty())
                .andExpect(jsonPath("$.songList[0].trackNumber").isEmpty())
                .andExpect(jsonPath("$.songList[0].displayOrder").value(10))
                .andExpect(jsonPath("$.songList[1].trackNumber").value(1))
                .andExpect(jsonPath("$.songList[2].discNumber").value(2))
                .andExpect(jsonPath("$.songList[2].trackNumber").value(4));
        mockMvc.perform(orderedTrack("602", "Invalid order", "null", "null", 0)).andExpect(status().isBadRequest());
        assertThat(songRepository.count()).isEqualTo(3);
    }

    @Test
    void concurrentPlaysIncrementOnlyTheCounter() throws Exception {
        mockMvc.perform(albumRequest()).andExpect(status().isOk());
        mockMvc.perform(trackRequest()).andExpect(status().isOk());
        var song = songRepository.findAll().get(0);
        song.setTitle("Reviewed title");
        song.setDescription("Keep reviewed metadata");
        songRepository.saveAndFlush(song);

        var workers = java.util.concurrent.Executors.newFixedThreadPool(4);
        var start = new java.util.concurrent.CountDownLatch(1);
        try {
            var tasks = new java.util.ArrayList<java.util.concurrent.Future<?>>();
            for (int i = 0; i < 4; i++) {
                tasks.add(workers.submit(() -> {
                    if (!start.await(10, java.util.concurrent.TimeUnit.SECONDS)) {
                        throw new IllegalStateException("Timed out waiting to start concurrent plays");
                    }
                    for (int play = 0; play < 10; play++) {
                        songService.incrementSongPlayCount(song.getId());
                    }
                    return null;
                }));
            }
            start.countDown();
            for (var task : tasks) {
                task.get(30, java.util.concurrent.TimeUnit.SECONDS);
            }
        } finally {
            workers.shutdownNow();
        }
        var updated = songRepository.findById(song.getId()).orElseThrow();
        assertThat(updated.getPlayCount()).isEqualTo(40L);
        assertThat(updated.getTitle()).isEqualTo("Reviewed title");
        assertThat(updated.getDescription()).isEqualTo("Keep reviewed metadata");
        assertThat(updated.getAudioPath()).isEqualTo(song.getAudioPath());
        assertThat(updated.getDisplayOrder()).isEqualTo(song.getDisplayOrder());
        assertThat(updated.getTrackNumber()).isEqualTo(song.getTrackNumber());
    }

    @Test
    void playsHandleNullCountersAndRejectUnknownSongs() throws Exception {
        mockMvc.perform(albumRequest()).andExpect(status().isOk());
        mockMvc.perform(trackRequest()).andExpect(status().isOk());
        var song = songRepository.findAll().get(0);
        song.setPlayCount(null);
        songRepository.saveAndFlush(song);
        mockMvc.perform(post("/user/song/{id}/play", song.getId())).andExpect(status().isAccepted());
        assertThat(songRepository.findById(song.getId()).orElseThrow().getPlayCount()).isEqualTo(1L);
        mockMvc.perform(post("/user/song/{id}/play", Long.MAX_VALUE)).andExpect(status().isNotFound());
        assertThat(songRepository.count()).isEqualTo(1);
    }

    @Test
    void staleEditsConflictBeforeMediaWritesButIdenticalLostResponsesSucceed() throws Exception {
        String albumPath = "/admin/catalog-import/kivo/albums/veritas-vol-2";
        mockMvc.perform(get(albumPath)).andExpect(status().isForbidden());
        mockMvc.perform(get(albumPath).header("X-Admin-Api-Key", KEY))
                .andExpect(status().isOk()).andExpect(jsonPath("$.exists").value(false));
        var albumResult = mockMvc.perform(albumRequest()).andExpect(status().isOk()).andReturn();
        String originalAlbumRevision = mapper.readTree(albumResult.getResponse().getContentAsString()).get("revision").asText();
        var first = mockMvc.perform(orderedTrack("600", "Reviewed title", "null", "null", 10)).andExpect(status().isOk()).andReturn();
        var receipt = mapper.readTree(first.getResponse().getContentAsString());
        String oldRevision = receipt.get("revision").asText();
        long songId = receipt.get("songId").asLong();
        mockMvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post("/user/song/{id}/play", songId))
                .andExpect(status().isAccepted());
        mockMvc.perform(get(albumPath + "/tracks/600").header("X-Admin-Api-Key", KEY))
                .andExpect(jsonPath("$.revision").value(oldRevision));
        var newer = orderedTrack("600", "Newer published correction", "null", "null", 10);
        newer.header("X-Catalog-Revision", oldRevision);
        var updated = mockMvc.perform(newer).andExpect(status().isOk()).andReturn();
        String newRevision = mapper.readTree(updated.getResponse().getContentAsString()).get("revision").asText();
        assertThat(newRevision).isNotEqualTo(oldRevision);
        var repeat = orderedTrack("600", "Newer published correction", "null", "null", 10);
        repeat.header("X-Catalog-Revision", oldRevision); // Lost response; do not require the unreceived revision.
        mockMvc.perform(repeat).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("unchanged"))
                .andExpect(jsonPath("$.songId").value(songId));
        long filesBefore;
        try (var paths = java.nio.file.Files.walk(mediaDirectory)) {
            filesBefore = paths.filter(java.nio.file.Files::isRegularFile).count();
        }
        var stale = orderedTrack("600", "Stale draft", "null", "null", 10, new byte[]{99, 98, 97});
        stale.header("X-Catalog-Revision", oldRevision);
        mockMvc.perform(stale).andExpect(status().isConflict())
                .andExpect(jsonPath("$.current.metadata.title").value("Newer published correction"))
                .andExpect(jsonPath("$.current.revision").value(newRevision));
        try (var paths = java.nio.file.Files.walk(mediaDirectory)) {
            assertThat(paths.filter(java.nio.file.Files::isRegularFile).count()).isEqualTo(filesBefore);
        }
        assertThat(songRepository.findById(songId).orElseThrow().getPlayCount()).isEqualTo(1);
        assertThat(songRepository.count()).isEqualTo(1);
        // An edit outside the import endpoint also changes the computed baseline.
        var album = albumRepository.findAll().get(0);
        album.setTitle("Newer album correction");
        albumRepository.saveAndFlush(album);
        var staleAlbum = albumRequest();
        staleAlbum.header("X-Catalog-Revision", originalAlbumRevision);
        mockMvc.perform(staleAlbum).andExpect(status().isConflict())
                .andExpect(jsonPath("$.current.metadata.title").value("Newer album correction"));
        String currentAlbumRevision = mapper.readTree(mockMvc.perform(get(albumPath).header("X-Admin-Api-Key", KEY))
                .andReturn().getResponse().getContentAsString()).get("revision").asText();
        var accepted = albumRequest();
        accepted.header("X-Catalog-Revision", currentAlbumRevision);
        mockMvc.perform(accepted).andExpect(status().isOk()).andExpect(jsonPath("$.created").value(false));
    }

    private MockMultipartHttpServletRequestBuilder orderedTrack(String id, String title, String disc, String position, int order) {
        return orderedTrack(id, title, disc, position, order, new byte[]{0, 1, 2, 3, 4, 5});
    }

    @Test
    void overlappingChangesFromOneBaselineHaveOnlyOneWinner() throws Exception {
        mockMvc.perform(albumRequest()).andExpect(status().isOk());
        var first = mockMvc.perform(orderedTrack("600", "Initial", "1", "1", 1)).andExpect(status().isOk()).andReturn();
        var receipt = mapper.readTree(first.getResponse().getContentAsString());
        String revision = receipt.get("revision").asText();
        long songId = receipt.get("songId").asLong();
        var start = new java.util.concurrent.CountDownLatch(1);
        var ready = new java.util.concurrent.CountDownLatch(2);
        var executor = java.util.concurrent.Executors.newFixedThreadPool(2);
        try {
            var attempts = new java.util.ArrayList<java.util.concurrent.Future<Integer>>();
            for (String title : java.util.List.of("Draft A", "Draft B")) {
                attempts.add(executor.submit(() -> {
                    ready.countDown();
                    if (!start.await(5, java.util.concurrent.TimeUnit.SECONDS)) throw new AssertionError("Start timed out");
                    var request = orderedTrack("600", title, "1", "1", 1);
                    request.header("X-Catalog-Revision", revision);
                    return mockMvc.perform(request).andReturn().getResponse().getStatus();
                }));
            }
            assertThat(ready.await(5, java.util.concurrent.TimeUnit.SECONDS)).isTrue();
            start.countDown();
            var statuses = new java.util.ArrayList<Integer>();
            for (var attempt : attempts) statuses.add(attempt.get(10, java.util.concurrent.TimeUnit.SECONDS));
            assertThat(statuses).containsExactlyInAnyOrder(200, 409);
        } finally {
            start.countDown();
            executor.shutdownNow();
        }
        assertThat(songRepository.count()).isEqualTo(1);
        assertThat(songRepository.findById(songId).orElseThrow().getTitle()).isIn("Draft A", "Draft B");
    }

    private MockMultipartHttpServletRequestBuilder orderedTrack(String id, String title, String disc, String position, int order, byte[] bytes) {
        MockMultipartHttpServletRequestBuilder request = multipart("/admin/catalog-import/kivo/albums/veritas-vol-2/tracks/" + id);
        request.with(item -> { item.setMethod("PUT"); return item; });
        request.header("X-Admin-Api-Key", KEY);
        request.file(json("metadata", """
                {"title":"%s","disc":%s,"position":%s,"displayOrder":%d,"kind":"bgm","artists":[],"composers":[],"performers":[]}
                """.formatted(title, disc, position, order)));
        request.file(file("audio", "audio.mp3", "audio/mpeg", bytes));
        return request;
    }

    private MockMultipartHttpServletRequestBuilder albumRequest() {
        MockMultipartHttpServletRequestBuilder request = multipart(
                "/admin/catalog-import/kivo/albums/veritas-vol-2");
        request.with(item -> { item.setMethod("PUT"); return item; });
        request.header("X-Admin-Api-Key", KEY);
        request.file(json("metadata", """
                {"title":"青春あんさんぶる Vol.2 「ヴェリタス」","category":"青春あんさんぶる","releaseDate":"2023-12-25","description":"reviewed"}
                """));
        request.file(file("coverOriginal", "cover.png", "image/png", new byte[]{1, 2}));
        request.file(file("cover400", "cover-400.jpg", "image/jpeg", new byte[]{3, 4}));
        request.file(file("cover800", "cover-800.jpg", "image/jpeg", new byte[]{5, 6}));
        return request;
    }

    private MockMultipartHttpServletRequestBuilder trackRequest() {
        MockMultipartHttpServletRequestBuilder request = multipart(
                "/admin/catalog-import/kivo/albums/veritas-vol-2/tracks/255");
        request.with(item -> { item.setMethod("PUT"); return item; });
        request.header("X-Admin-Api-Key", KEY);
        request.file(json("metadata", """
                {"title":"Get Over the World","disc":1,"position":1,"displayOrder":20,"kind":"vocal","description":"","artists":["Veritas"],"composers":["Veritas","Nor"],"performers":[{"character":"チヒロ","voiceActor":"山村響"}]}
                """));
        request.file(file("audio", "audio.mp3", "audio/mpeg", new byte[]{0, 1, 2, 3, 4, 5}));
        return request;
    }

    private MockMultipartFile json(String name, String value) {
        return new MockMultipartFile(name, "metadata.json", MediaType.APPLICATION_JSON_VALUE, value.getBytes());
    }

    private MockMultipartFile file(String name, String filename, String type, byte[] value) {
        return new MockMultipartFile(name, filename, type, value);
    }
}
