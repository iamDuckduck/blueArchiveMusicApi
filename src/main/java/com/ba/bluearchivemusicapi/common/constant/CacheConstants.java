package com.ba.bluearchivemusicapi.common.constant;

import java.time.Duration;

public class CacheConstants {
    // Cache names
    public static final String AUDIO_URL_CACHE = "audioUrls";
    public static final String PLAYCOUNT_CACHE = "playCounts";

    // TTL durations
    public static final Duration AUDIO_URL_CACHE_TTL = Duration.ofMinutes(40);
    public static final Duration DEFAULT_CACHE_TTL = Duration.ofMinutes(10);
}
