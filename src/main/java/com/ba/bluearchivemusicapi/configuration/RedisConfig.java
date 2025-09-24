package com.ba.bluearchivemusicapi.configuration;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.GenericToStringSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;

import java.util.HashMap;
import java.util.Map;

import static com.ba.bluearchivemusicapi.common.constant.CacheConstants.*;

@Configuration
public class RedisConfig {

    @Bean
    public RedisTemplate<String, Integer> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Integer> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);
        template.setKeySerializer(new StringRedisSerializer());
        template.setValueSerializer(new GenericToStringSerializer<>(Integer.class));
        return template;
    }

    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory redisConnectionFactory) {
        // default setting
        RedisCacheConfiguration redisCacheConfiguration = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(DEFAULT_CACHE_TTL)
                .disableCachingNullValues()
                .serializeValuesWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new GenericJackson2JsonRedisSerializer()));  // This handles any object

        // config for audioUrl caching
        RedisCacheConfiguration audioUrlTtlConfig = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(AUDIO_URL_CACHE_TTL)
                .disableCachingNullValues()
                .serializeValuesWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new StringRedisSerializer()));

        // config for playCount caching
        RedisCacheConfiguration playCountConfig = RedisCacheConfiguration.defaultCacheConfig()
                .disableCachingNullValues()
                .serializeValuesWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new GenericToStringSerializer<>(Integer.class)));

        // assign keys to custom config settings
        Map<String, RedisCacheConfiguration> cacheConfigurations = new HashMap<>();
        cacheConfigurations.put(AUDIO_URL_CACHE, audioUrlTtlConfig);
        cacheConfigurations.put(PLAYCOUNT_CACHE, playCountConfig);

        return RedisCacheManager
                .builder(redisConnectionFactory)
                .cacheDefaults(redisCacheConfiguration)
                .withInitialCacheConfigurations(cacheConfigurations)
                .build();
    }
}