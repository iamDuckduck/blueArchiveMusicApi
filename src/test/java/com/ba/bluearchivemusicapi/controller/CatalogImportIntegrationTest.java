package com.ba.bluearchivemusicapi.controller;

import com.ba.bluearchivemusicapi.repositories.AlbumRepository;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import com.ba.bluearchivemusicapi.scheduler.SongPlayCountScheduledTask;
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
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMultipartHttpServletRequestBuilder;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
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

    @MockitoBean SongPlayCountScheduledTask playCountScheduledTask;

    @Autowired MockMvc mockMvc;
    @Autowired AlbumRepository albumRepository;
    @Autowired SongRepository songRepository;

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
        // Existing plays are database state here; the normal Redis counting flow is unchanged.
        var existingSong = songRepository.findById(songId).orElseThrow();
        existingSong.setPlayCount(7L);
        songRepository.saveAndFlush(existingSong);
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

    private MockMultipartHttpServletRequestBuilder orderedTrack(String id, String title, String disc, String position, int order) {
        MockMultipartHttpServletRequestBuilder request = multipart("/admin/catalog-import/kivo/albums/veritas-vol-2/tracks/" + id);
        request.with(item -> { item.setMethod("PUT"); return item; });
        request.header("X-Admin-Api-Key", KEY);
        request.file(json("metadata", """
                {"title":"%s","disc":%s,"position":%s,"displayOrder":%d,"kind":"bgm","artists":[],"composers":[],"performers":[]}
                """.formatted(title, disc, position, order)));
        request.file(file("audio", "audio.mp3", "audio/mpeg", new byte[]{0, 1, 2, 3, 4, 5}));
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
