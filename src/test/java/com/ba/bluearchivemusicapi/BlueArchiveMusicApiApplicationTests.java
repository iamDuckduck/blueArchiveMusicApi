package com.ba.bluearchivemusicapi;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import com.ba.bluearchivemusicapi.scheduler.SongPlayCountScheduledTask;

@SpringBootTest
@ActiveProfiles("test")
class BlueArchiveMusicApiApplicationTests {

    // Loading the context must not start background Redis writes.
    @MockitoBean
    SongPlayCountScheduledTask playCountScheduledTask;

    @Test
    void contextLoads() {
    }

}
