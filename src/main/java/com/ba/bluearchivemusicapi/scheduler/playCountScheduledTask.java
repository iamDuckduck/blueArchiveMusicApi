package com.ba.bluearchivemusicapi.scheduler;

import com.ba.bluearchivemusicapi.entities.OST;
import com.ba.bluearchivemusicapi.repositories.OstRepository;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static com.ba.bluearchivemusicapi.common.constant.CacheConstants.PLAYCOUNT_CACHE;

@Slf4j
@AllArgsConstructor
@Component
public class playCountScheduledTask {

//    private OstRepository ostRepository;
//
//    private RedisTemplate<String, Integer> redisTemplate;
//
//    @Scheduled(fixedRate = 60000) // 1 minutes in ms
//    @Transactional
//    public void syncPlayCount() {
//        log.info("syncPlayCount (ScheduledTask)");
//
//        // find playCounts key
//        Set<String> keys = redisTemplate.keys(PLAYCOUNT_CACHE + "*");
//
//        // create a map to store ost ID and corresponding increment playCount
//        Map<String, Integer> playCountMap = new HashMap<>();
//
//        if (!keys.isEmpty()) {
//            for (String key : keys) {
//                Integer value = redisTemplate.opsForValue().get(key);
//                String id = key.split("::")[1];
//                playCountMap.put(id, value);
//            }
//        }
//
//        log.info(playCountMap.toString());
//
//        // Convert Map keys (String) to List<Long> for IDs
//        List<Long> ids = playCountMap.keySet().stream()
//                .map(Long::valueOf)
//                .toList();
//
//        // get related ost
//        List<OST> osts = ostRepository.findByIdIn(ids);
//
//        // batch update them
//        osts.forEach(ost -> {
//            Long id = ost.getId();
//            Integer currentPlayCount = ost.getPlayCount();
//            Integer increment = playCountMap.get(id.toString());
//            ost.setPlayCount(currentPlayCount + increment);
//        });
//
//        // Save all updated entities (Hibernate handles batching)
//        ostRepository.saveAll(osts);
//
//        // invalid cache
//        redisTemplate.delete(keys);
//        log.info("delete playCount cache");
//    }
}