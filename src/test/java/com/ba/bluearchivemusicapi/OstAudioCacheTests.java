package com.ba.bluearchivemusicapi;

import com.ba.bluearchivemusicapi.common.constant.CacheConstants;
import com.ba.bluearchivemusicapi.repositories.OstRepository;
import com.ba.bluearchivemusicapi.repositories.OstTypeRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;

import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;

import java.util.concurrent.TimeUnit;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
@AutoConfigureMockMvc
public class OstAudioCacheTests {

    // Inject MockMvc to simulate HTTP requests
    @Autowired
    private MockMvc mockMvc;

    // Inject cacheManager to get cache value
    @Autowired
    private CacheManager cacheManager;

    // Inject redisTemplate to check ttl
    @Autowired
    private StringRedisTemplate redisTemplate;

    @Autowired
    private ObjectMapper objectMapper; // For converting DTO to JSON

    // Set up Redis container
    @Container
    @ServiceConnection
    static GenericContainer redis = new GenericContainer(DockerImageName.parse("redis:7.4.2"))
            .withExposedPorts(6379);
    @Autowired
    private OstRepository ostRepository;
    @Autowired
    private OstTypeRepository ostTypeRepository;

    @Test
    void testUserAudioUrlCache() throws Exception {
        final Long ostId = 8L;

        // Step 1: Perform a GET request to /audio/8
        MvcResult result = mockMvc.perform(get("/user/ost/audio/" + ostId))
                .andExpect(status().isOk())
                .andExpect(content().contentType("text/plain;charset=UTF-8"))
                .andReturn();

        // Step 2: Extract and verify the response body
        String responseBody = result.getResponse().getContentAsString();
        assertNotNull(responseBody, "Response body should not be null");

        // Step 3: Check Cache
        Cache cache = cacheManager.getCache(CacheConstants.AUDIO_URL_CACHE);
        assertNotNull(cache);
        assertNotNull(cache.get(ostId, String.class));

        // Step 4: Check Cache's value
        assertEquals(responseBody, cache.get(ostId, String.class));

        // Step 5: Get and verify TTL (should around 40 mins)
        String cacheKey = CacheConstants.AUDIO_URL_CACHE + "::" + ostId;
        Long ttl = redisTemplate.getExpire(cacheKey, TimeUnit.SECONDS);
        assertNotNull(ttl, "TTL should exist for cache key");

        long expectedTtlSeconds = CacheConstants.AUDIO_URL_CACHE_TTL.getSeconds();
        assertTrue(ttl >= expectedTtlSeconds - 5 && ttl <= expectedTtlSeconds + 5,
                "TTL should be approximately " + expectedTtlSeconds + " seconds, but was " + ttl);
    }

    // with @Transactional, it rolls back the changes in the db
    @Test
    @Transactional
    void testUserAudioUrlInvalidCacheAfterUpdating() throws Exception {
        final Long ostId = 8L;

        // Step 1: Perform a GET request to /audio/8
        mockMvc.perform(get("/user/ost/audio/" + ostId))
                .andExpect(status().isOk())
                .andExpect(content().contentType("text/plain;charset=UTF-8"))
                .andReturn();

        // Step 2: Admin Updates OST (id: 8)
        mockMvc.perform(multipart("/admin/ost/edit/" + ostId)
                        .param("ostNumber", "1")
                        .param("name", "Test OST")
                        .param("author", "Test Author")
                        .param("image_path", "OST/coverImages/429ee2ee-e8e6-4079-81a3-ea1e0d32292d-ブルーアーカイブ blue archive ost 2. luminous memory.png")
                        .param("audio_path", "OST/audio/882d0c9c-6bda-495f-813d-78f6f7e59ff2-ブルーアーカイブ blue archive ost 2. luminous memory.mp3")
                        .param("ostTypeName", "Longing for the memorable days")
                        .with(request -> { request.setMethod("PUT"); return request; }))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON));

        // Step 3: should invalid Cache
        Cache cache = cacheManager.getCache(CacheConstants.AUDIO_URL_CACHE);
        assertNull(cache.get(ostId, String.class));
    }
}
