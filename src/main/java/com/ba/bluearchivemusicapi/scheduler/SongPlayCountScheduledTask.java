package com.ba.bluearchivemusicapi.scheduler;

import com.ba.bluearchivemusicapi.entities.Song;
import com.ba.bluearchivemusicapi.repositories.SongRepository;
import org.springframework.dao.DataAccessException;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static com.ba.bluearchivemusicapi.common.constant.CacheConstants.SONG_PLAYCOUNT_CACHE;

@Component
public class SongPlayCountScheduledTask {

    private static final Logger log = LoggerFactory.getLogger(SongPlayCountScheduledTask.class);
    private static final String CACHE_KEY_SEPARATOR = "::";

    private final SongRepository songRepository;

    private final RedisTemplate<String, Integer> redisTemplate;

    public SongPlayCountScheduledTask(SongRepository songRepository, RedisTemplate<String, Integer> redisTemplate) {
        this.songRepository = songRepository;
        this.redisTemplate = redisTemplate;
    }

    // Keep demo infrastructure quiet: an hourly sync avoids constant Redis polling.
    // On an idle-sleep host such as Render, a sleeping service runs no scheduler or Redis calls.
    @Scheduled(fixedRate = 60 * 60 * 1000)
    @Transactional
    public void syncPlayCount() {
        log.info("syncSongPlayCount (ScheduledTask)");

        Map<Long, Integer> playCountIncrements = drainSongPlayCountIncrements();
        if (playCountIncrements.isEmpty()) {
            return;
        }

        try {
            List<Song> songs = songRepository.findAllById(playCountIncrements.keySet());

            // Hibernate can batch these UPDATE statements with hibernate.jdbc.batch_size,
            // while flush surfaces DB failures before Redis counts are lost.
            songs.forEach(song -> {
                Integer increment = playCountIncrements.get(song.getId());
                song.setPlayCount(song.getPlayCount() + increment);
            });
            songRepository.saveAllAndFlush(songs);

            if (songs.size() < playCountIncrements.size()) {
                log.warn("Synced {} song play-count keys, but only {} song rows were found",
                        playCountIncrements.size(), songs.size());
            }
            log.info("Synced {} song play-count keys", songs.size());
        } catch (DataAccessException ex) {
            restoreSongPlayCountIncrements(playCountIncrements);
            throw ex;
        }
    }

    private Map<Long, Integer> drainSongPlayCountIncrements() {
        Map<Long, Integer> playCountIncrements = new HashMap<>();

        Set<String> keys = redisTemplate.keys(SONG_PLAYCOUNT_CACHE + CACHE_KEY_SEPARATOR + "*");
        if (keys.isEmpty()) {
            return playCountIncrements;
        }

        for (String key : keys) {
            Long songId = parseSongId(key);

            // GETDEL reads and deletes in one Redis operation. That prevents losing a new play that happens
            // between a separate GET and DELETE, because the new play recreates the key for the next sync.
            Integer increment = redisTemplate.opsForValue().getAndDelete(key);
            if (increment != null && increment > 0) {
                playCountIncrements.put(songId, increment);
            }
        }

        return playCountIncrements;
    }

    private Long parseSongId(String key) {
        String id = key.substring(key.lastIndexOf(CACHE_KEY_SEPARATOR) + CACHE_KEY_SEPARATOR.length());
        return Long.valueOf(id);
    }

    private void restoreSongPlayCountIncrements(Map<Long, Integer> playCountIncrements) {
        playCountIncrements.forEach((songId, increment) ->
                redisTemplate.opsForValue().increment(
                        SONG_PLAYCOUNT_CACHE + CACHE_KEY_SEPARATOR + songId,
                        increment
                )
        );
    }
}
