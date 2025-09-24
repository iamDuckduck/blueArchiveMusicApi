package com.ba.bluearchivemusicapi;

import com.ba.bluearchivemusicapi.common.constant.CacheConstants;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
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

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
@AutoConfigureMockMvc
public class OstPlayCountCacheTests {

    // Inject MockMvc to simulate HTTP requests
    @Autowired
    private MockMvc mockMvc;

    // Inject cacheManager to get cache value
    @Autowired
    private CacheManager cacheManager;

    // Inject redisTemplate to check ttl
    @Autowired
    private RedisTemplate<String, Integer> redisTemplate;

    // Set up Redis container
    @Container
    @ServiceConnection
    static GenericContainer redis = new GenericContainer(DockerImageName.parse("redis:7.4.2"))
            .withExposedPorts(6379);

    @Test
    void testUserPlayCountCache() throws Exception {
        final long ostId = 8L;
        String cacheKey = CacheConstants.PLAYCOUNT_CACHE + "::" + ostId;

        // Clear cache before test
        Cache cache = cacheManager.getCache(CacheConstants.PLAYCOUNT_CACHE);
        if (cache != null) {
            cache.clear();
        }

        // Step 1: Perform a GET request to /audio/8
        MvcResult result = mockMvc.perform(get("/user/ost/audio/" + ostId))
                .andExpect(status().isOk())
                .andExpect(content().contentType("text/plain;charset=UTF-8"))
                .andReturn();

        // Step 2: Extract and verify the response body
        String responseBody = result.getResponse().getContentAsString();
        assertNotNull(responseBody, "Response body should not be null");

        // Step 3: Check Cache
        // Check Redis value and type
        Integer value = redisTemplate.opsForValue().get(cacheKey);
        assertNotNull(value);

        // Step 4: Check Cache's value
        assertEquals(1, value);
    }
}
